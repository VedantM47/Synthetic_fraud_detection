"""Background job execution with live, persisted progress."""

from __future__ import annotations

import logging
import threading
import time
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

from backend.db import Database, utcnow
from backend.pipeline.ingest import IngestError
from backend.pipeline.modeling import PipelineError
from backend.pipeline.runner import run_analysis, stage_plan

logger = logging.getLogger("fraud.jobs")

PROGRESS_WRITE_INTERVAL = 0.25


class JobContext:
    """Progress reporter handed to the pipeline; writes to the jobs table."""

    def __init__(self, db: Database, job_id: str, stages: list[dict]):
        self.db = db
        self.job_id = job_id
        self.stages = stages
        self.current: dict | None = None
        self._last_write = 0.0
        self._last_message: str | None = None

    def _overall(self) -> float:
        return min(1.0, sum(stage["weight"] * stage["progress"] for stage in self.stages))

    def _write(self, force: bool = False) -> None:
        # A new message is always persisted (it may be followed by a long
        # silent step); pure progress ticks are throttled.
        now = time.monotonic()
        message = self.current["message"] if self.current else None
        if not force and message == self._last_message and now - self._last_write < PROGRESS_WRITE_INTERVAL:
            return
        self._last_write = now
        self._last_message = message
        self.db.update_job(
            self.job_id,
            progress=round(self._overall(), 4),
            stage=self.current["key"] if self.current else None,
            message=self.current["message"] if self.current else None,
            stages=self.stages,
        )

    @contextmanager
    def stage(self, key: str):
        stage = next(item for item in self.stages if item["key"] == key)
        stage.update(status="running", started_at=utcnow(), progress=0.0)
        self.current = stage
        self._write(force=True)
        try:
            yield
        except Exception:
            stage["status"] = "failed"
            self._write(force=True)
            raise
        stage.update(status="done", progress=1.0, finished_at=utcnow())
        self._write(force=True)

    def progress(self, fraction: float, message: str) -> None:
        if self.current is None:
            return
        self.current["progress"] = max(self.current["progress"], min(1.0, max(0.0, float(fraction))))
        self.current["message"] = message
        self._write(force=fraction >= 1.0)


class JobManager:
    def __init__(self, db: Database, paths: dict[str, Path]):
        self.db = db
        self.paths = paths
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fraud-job")
        self.futures: dict[str, Future] = {}
        self._lock = threading.Lock()

    def submit(self, kind: str, dataset_id: str, params: dict | None = None) -> str:
        job_id = uuid.uuid4().hex[:12]
        params = dict(params or {})
        params["job_id"] = job_id
        self.db.create_job(job_id, dataset_id, kind, stage_plan(kind), params)
        future = self.executor.submit(self._run, job_id, kind, dataset_id, params)
        with self._lock:
            self.futures[job_id] = future
        return job_id

    def wait(self, job_id: str, timeout: float | None = None) -> dict:
        with self._lock:
            future = self.futures.get(job_id)
        if future is not None:
            future.result(timeout=timeout)
        return self.db.get_job(job_id)

    def active_job(self, dataset_id: str) -> dict | None:
        rows = self.db.all(
            "SELECT * FROM jobs WHERE dataset_id = ? AND status IN ('queued', 'running') ORDER BY created_at LIMIT 1",
            (dataset_id,),
        )
        return rows[0] if rows else None

    def _run(self, job_id: str, kind: str, dataset_id: str, params: dict) -> None:
        job = self.db.get_job(job_id)
        context = JobContext(self.db, job_id, job["stages"])
        self.db.update_job(job_id, status="running", started_at=utcnow(), message="Starting")
        self.db.update_dataset(dataset_id, status="processing")
        try:
            result = run_analysis(context, self.db, self.paths, dataset_id, kind, params)
        except (IngestError, PipelineError) as error:
            self._fail(job_id, dataset_id, str(error), context)
            return
        except Exception as error:  # pragma: no cover - unexpected failures are logged
            logger.error("Job %s failed:\n%s", job_id, traceback.format_exc())
            self._fail(job_id, dataset_id, f"Unexpected error: {error}", context)
            return
        self.db.update_job(
            job_id,
            status="completed",
            progress=1.0,
            message="Finished",
            stages=context.stages,
            result=result,
            finished_at=utcnow(),
        )

    def _fail(self, job_id: str, dataset_id: str, message: str, context: JobContext) -> None:
        self.db.update_job(
            job_id,
            status="failed",
            error=message,
            message=message,
            stages=context.stages,
            finished_at=utcnow(),
        )
        dataset = self.db.get_dataset(dataset_id)
        if dataset is not None:
            has_results = int(dataset["active_version"] or 0) > 0
            self.db.update_dataset(dataset_id, status="ready" if has_results else "failed", error=message)

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
