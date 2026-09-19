"""FastAPI application: REST API, live job progress (SSE) and the built frontend."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import re
import shutil
import uuid
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend import settings
from backend.db import Database, dumps
from backend.jobs import JobManager
from backend.pipeline.ingest import (
    CUSTOMER_ROLES,
    IDENTITY_ROLES,
    IngestError,
    preview_file,
    read_table,
    validate_customer_roles,
)

UPLOAD_KINDS = ["customers", "links", "events"]
SAFE_ID = re.compile(r"^[a-f0-9]{8,32}$")


class SyntheticRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    n_legitimate: int = Field(default=8000, ge=200, le=50_000)
    n_fraud: int = Field(default=800, ge=20, le=10_000)


class CreateDatasetRequest(BaseModel):
    upload_id: str
    name: str = Field(min_length=1, max_length=120)
    mapping: dict


class ReviewRequest(BaseModel):
    decision: Literal["confirm", "dismiss", "reset"]
    note: str = Field(default="", max_length=2000)
    include: list[str] | None = None


def _job_public(job: dict | None) -> dict | None:
    if job is None:
        return None
    return {
        key: job.get(key)
        for key in [
            "id",
            "dataset_id",
            "kind",
            "status",
            "progress",
            "stage",
            "message",
            "stages",
            "error",
            "result",
            "created_at",
            "started_at",
            "finished_at",
        ]
    }


def create_app(storage_dir: Path | None = None) -> FastAPI:
    paths = settings.storage_paths(storage_dir)
    for key in ["base", "uploads", "datasets", "reference"]:
        paths[key].mkdir(parents=True, exist_ok=True)
    db = Database(paths["db"])
    db.fail_interrupted_jobs()
    jobs = JobManager(db, paths)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        jobs.shutdown()

    app = FastAPI(title="Fraud Ring Detection API", version="1.0.0", lifespan=lifespan)
    app.state.db = db
    app.state.jobs = jobs
    app.state.paths = paths

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_dataset_or_404(dataset_id: str) -> dict:
        dataset = db.get_dataset(dataset_id)
        if dataset is None:
            raise HTTPException(404, "Dataset not found.")
        return dataset

    def require_results(dataset_id: str) -> dict:
        dataset = get_dataset_or_404(dataset_id)
        if not dataset["active_version"]:
            raise HTTPException(409, "This dataset has not finished processing yet.")
        return dataset

    def active_run(dataset: dict) -> dict | None:
        return db.one(
            "SELECT * FROM model_runs WHERE dataset_id = ? AND version = ?",
            (dataset["id"], dataset["active_version"]),
        )

    def ring_statuses(dataset_id: str) -> dict[str, dict]:
        statuses = {}
        for (target_type, target_id), review in db.review_status(dataset_id).items():
            if target_type != "ring":
                continue
            decision = review["decision"]
            statuses[target_id] = {
                "status": {"confirm": "confirmed", "dismiss": "dismissed"}.get(decision, "pending"),
                "reviewed_at": review["created_at"] if decision != "reset" else None,
                "note": review["note"],
            }
        return statuses

    def customer_brief(row: dict, feedback: dict[str, int]) -> dict:
        return {
            "customer_id": row["customer_id"],
            "name": row["name"],
            "risk": row["risk"],
            "risk_level": row["risk_level"],
            "rank": row["rank"],
            "ring_id": row["ring_id"],
            "degree": row["degree"],
            "high_neighbors": row["high_neighbors"],
            "top_reason": row["top_reason"],
            "label": row["label"],
            "analyst_label": feedback.get(row["customer_id"]),
        }

    def feedback_summary(dataset: dict) -> dict:
        labels = db.feedback_labels(dataset["id"])
        reviews = db.reviews(dataset["id"])
        run = active_run(dataset)
        since = [review for review in reviews if (review["model_version"] or 0) >= (dataset["active_version"] or 0)]
        used = run["n_feedback"] if run else 0
        return {
            "n_labels": len(labels),
            "fraud": sum(1 for value in labels.values() if value == 1),
            "legit": sum(1 for value in labels.values() if value == 0),
            "n_reviews": len(reviews),
            "reviews_since_model": len(since),
            "labels_in_model": used,
            "retrain_recommended": len(since) > 0,
        }

    def ring_row_public(row: dict, statuses: dict[str, dict]) -> dict:
        status = statuses.get(row["ring_id"], {"status": "pending", "reviewed_at": None, "note": None})
        return {
            "ring_id": row["ring_id"],
            "size": row["size"],
            "n_edges": row["n_edges"],
            "density": row["density"],
            "score": row["score"],
            "max_risk": row["max_risk"],
            "n_high": row["n_high"],
            "suspected": bool(row["suspected"]),
            "shared_types": row["shared_types"],
            "explanation": row["explanation"],
            "truth": row["truth"],
            "open_span_days": row["open_span_days"],
            "status": status["status"],
            "reviewed_at": status["reviewed_at"],
            "review_note": status["note"],
        }

    def graph_payload(dataset_id: str, node_ids: list[str], feedback: dict[str, int], extra: dict | None = None) -> dict:
        if not node_ids:
            return {"nodes": [], "edges": []}
        wanted = set(node_ids)
        rows = []
        edges = []
        with db.connect() as connection:
            connection.execute("CREATE TEMP TABLE wanted (id TEXT PRIMARY KEY)")
            connection.executemany("INSERT OR IGNORE INTO wanted VALUES (?)", [(node,) for node in wanted])
            rows = [
                dict(row)
                for row in connection.execute(
                    "SELECT customer_id, name, risk, risk_level, ring_id, label, degree FROM customers "
                    "WHERE dataset_id = ? AND customer_id IN (SELECT id FROM wanted)",
                    (dataset_id,),
                )
            ]
            edges = [
                dict(row)
                for row in connection.execute(
                    "SELECT source, target, types, weight FROM edges WHERE dataset_id = ? "
                    "AND source IN (SELECT id FROM wanted) AND target IN (SELECT id FROM wanted)",
                    (dataset_id,),
                )
            ]
        nodes = [
            {
                "id": row["customer_id"],
                "name": row["name"],
                "risk": row["risk"],
                "level": row["risk_level"],
                "ring_id": row["ring_id"],
                "label": row["label"],
                "analyst_label": feedback.get(row["customer_id"]),
                "degree": row["degree"],
                **((extra or {}).get(row["customer_id"], {})),
            }
            for row in rows
        ]
        return {
            "nodes": nodes,
            "edges": [
                {"source": edge["source"], "target": edge["target"], "types": edge["types"].split(","), "weight": edge["weight"]}
                for edge in edges
            ],
        }

    def neighbors(dataset_id: str, customer_id: str) -> list[dict]:
        return db.all(
            "SELECT target AS other, types, weight FROM edges WHERE dataset_id = ? AND source = ? "
            "UNION ALL SELECT source AS other, types, weight FROM edges WHERE dataset_id = ? AND target = ?",
            (dataset_id, customer_id, dataset_id, customer_id),
        )

    # ------------------------------------------------------------------
    # Health, uploads, datasets
    # ------------------------------------------------------------------

    @app.get("/api/health")
    def health():
        return {"status": "ok", "datasets": len(db.list_datasets())}

    @app.get("/api/roles")
    def roles():
        return {"customer_roles": CUSTOMER_ROLES, "identity_roles": IDENTITY_ROLES}

    @app.post("/api/uploads")
    async def upload_files(
        customers: UploadFile = File(...),
        links: UploadFile | None = File(default=None),
        events: UploadFile | None = File(default=None),
    ):
        upload_id = uuid.uuid4().hex
        folder = paths["uploads"] / upload_id
        folder.mkdir(parents=True)
        manifest = {}
        try:
            for kind, upload in [("customers", customers), ("links", links), ("events", events)]:
                if upload is None or not upload.filename:
                    continue
                target = folder / f"{kind}.csv"
                size = 0
                with open(target, "wb") as handle:
                    while chunk := await upload.read(1024 * 1024):
                        size += len(chunk)
                        if size > settings.MAX_UPLOAD_BYTES:
                            raise IngestError(
                                f"{upload.filename}: larger than {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
                            )
                        handle.write(chunk)
                if Path(upload.filename).suffix.lower() in {".xlsx", ".xls", ".xlsm", ".parquet", ".json"}:
                    raise IngestError(f"{upload.filename}: please export the file as CSV.")
                manifest[kind] = {"filename": upload.filename, "bytes": size}
            previews = {}
            for kind in manifest:
                preview = await run_in_threadpool(preview_file, folder / f"{kind}.csv", kind)
                preview["filename"] = manifest[kind]["filename"]
                previews[kind] = preview
        except IngestError as error:
            shutil.rmtree(folder, ignore_errors=True)
            raise HTTPException(400, str(error)) from error
        (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return {"upload_id": upload_id, "files": previews}

    @app.get("/api/datasets")
    def list_datasets():
        result = []
        for dataset in db.list_datasets():
            result.append(
                {
                    **{key: dataset[key] for key in ["id", "name", "source", "created_at", "status", "error", "active_version"]},
                    "summary": dataset["summary"],
                    "active_job": _job_public(jobs.active_job(dataset["id"])),
                }
            )
        return result

    @app.post("/api/datasets", status_code=201)
    def create_dataset(request: CreateDatasetRequest):
        if not SAFE_ID.match(request.upload_id):
            raise HTTPException(400, "Invalid upload id.")
        folder = paths["uploads"] / request.upload_id
        manifest_path = folder / "manifest.json"
        if not manifest_path.is_file():
            raise HTTPException(404, "Upload not found; please upload the files again.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        mapping = request.mapping or {}
        roles = (mapping.get("customers") or {}).get("roles") or {}
        try:
            header = read_table(folder / "customers.csv", nrows=5)
            validate_customer_roles(header, roles)
        except IngestError as error:
            raise HTTPException(400, str(error)) from error
        has_identity = any(role in IDENTITY_ROLES for role in roles.values())
        has_links = "links" in manifest and bool(mapping.get("links"))
        has_events = "events" in manifest and bool(mapping.get("events"))
        has_label = "label" in roles.values()
        has_features = "feature" in roles.values() or "open_date" in roles.values()
        if not (has_identity or has_links or has_events or (has_label and has_features)):
            raise HTTPException(
                400,
                "Nothing to analyse: map at least one identity column (phone, email, address, device, ...), "
                "add an identity-links or events file, or map a fraud label plus numeric features.",
            )
        for kind, required in [("links", ["customer_id", "attribute_type", "attribute_value"]), ("events", ["customer_id", "event_date"])]:
            if mapping.get(kind) and kind in manifest:
                missing = [field for field in required if not mapping[kind].get(field)]
                if missing:
                    raise HTTPException(400, f"{kind} file: choose a column for {', '.join(missing)}.")

        dataset_id = uuid.uuid4().hex[:10]
        target = paths["datasets"] / dataset_id / "uploads"
        target.mkdir(parents=True)
        files = {}
        for kind in UPLOAD_KINDS:
            if kind in manifest and (kind == "customers" or mapping.get(kind)):
                shutil.copy2(folder / f"{kind}.csv", target / f"{kind}.csv")
                files[kind] = str(target / f"{kind}.csv")
        shutil.rmtree(folder, ignore_errors=True)
        stored_mapping = {**mapping, "filenames": {kind: manifest[kind]["filename"] for kind in files}}
        db.create_dataset(dataset_id, request.name.strip(), "upload", stored_mapping, files)
        job_id = jobs.submit("analyze", dataset_id)
        return {"dataset_id": dataset_id, "job_id": job_id}

    @app.post("/api/datasets/synthetic", status_code=201)
    def create_synthetic(request: SyntheticRequest):
        if request.n_fraud > request.n_legitimate:
            raise HTTPException(400, "Use fewer fraud-ring customers than legitimate customers.")
        dataset_id = uuid.uuid4().hex[:10]
        name = request.name or f"Synthetic demo (seed {request.seed})"
        params = {"seed": request.seed, "n_legitimate": request.n_legitimate, "n_fraud": request.n_fraud}
        db.create_dataset(dataset_id, name, "synthetic", {"synthetic": params}, None)
        job_id = jobs.submit("synthetic", dataset_id, params)
        return {"dataset_id": dataset_id, "job_id": job_id}

    @app.get("/api/datasets/{dataset_id}")
    def get_dataset(dataset_id: str):
        dataset = get_dataset_or_404(dataset_id)
        run = active_run(dataset)
        return {
            **{key: dataset[key] for key in ["id", "name", "source", "created_at", "status", "error", "active_version"]},
            "summary": dataset["summary"],
            "mapping": dataset["mapping"],
            "active_job": _job_public(jobs.active_job(dataset_id)),
            "model": None
            if run is None
            else {
                "version": run["version"],
                "mode": run["mode"],
                "threshold": run["threshold"],
                "created_at": run["created_at"],
                "n_feedback": run["n_feedback"],
            },
            "feedback": feedback_summary(dataset),
        }

    @app.delete("/api/datasets/{dataset_id}", status_code=204)
    def delete_dataset(dataset_id: str):
        get_dataset_or_404(dataset_id)
        if jobs.active_job(dataset_id):
            raise HTTPException(409, "Wait for the running job to finish before deleting this dataset.")
        db.delete_dataset(dataset_id)
        shutil.rmtree(paths["datasets"] / dataset_id, ignore_errors=True)

    @app.post("/api/datasets/{dataset_id}/retrain", status_code=201)
    def retrain(dataset_id: str):
        require_results(dataset_id)
        if jobs.active_job(dataset_id):
            raise HTTPException(409, "A job is already running for this dataset.")
        return {"dataset_id": dataset_id, "job_id": jobs.submit("retrain", dataset_id)}

    # ------------------------------------------------------------------
    # Jobs and live progress
    # ------------------------------------------------------------------

    @app.get("/api/jobs")
    def list_jobs(dataset_id: str | None = None, limit: int = Query(20, ge=1, le=200)):
        return [_job_public(job) for job in db.list_jobs(dataset_id, limit)]

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        job = db.get_job(job_id)
        if job is None:
            raise HTTPException(404, "Job not found.")
        return _job_public(job)

    @app.get("/api/jobs/{job_id}/stream")
    async def stream_job(job_id: str, request: Request):
        if db.get_job(job_id) is None:
            raise HTTPException(404, "Job not found.")

        async def events():
            last_payload = None
            idle = 0.0
            while True:
                if await request.is_disconnected():
                    break
                job = await run_in_threadpool(db.get_job, job_id)
                payload = dumps(_job_public(job))
                if payload != last_payload:
                    yield f"data: {payload}\n\n"
                    last_payload = payload
                    idle = 0.0
                elif idle >= 10:
                    yield ": keep-alive\n\n"
                    idle = 0.0
                if job is None or job["status"] in {"completed", "failed"}:
                    break
                await asyncio.sleep(0.4)
                idle += 0.4

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    @app.get("/api/datasets/{dataset_id}/overview")
    def overview(dataset_id: str):
        dataset = require_results(dataset_id)
        run = active_run(dataset)
        metrics = run["metrics"]
        feedback = db.feedback_labels(dataset_id)
        statuses = ring_statuses(dataset_id)
        suspected = db.all(
            "SELECT * FROM rings WHERE dataset_id = ? AND suspected = 1 ORDER BY score DESC, size DESC",
            (dataset_id,),
        )
        reviewed = [ring for ring in suspected if statuses.get(ring["ring_id"], {}).get("status") in {"confirmed", "dismissed"}]
        top_customers = db.all(
            "SELECT * FROM customers WHERE dataset_id = ? ORDER BY rank LIMIT 10", (dataset_id,)
        )
        evaluation = metrics.get("evaluation") or {}
        return {
            "dataset": {"id": dataset["id"], "name": dataset["name"], "source": dataset["source"], "summary": dataset["summary"]},
            "model": {
                "version": run["version"],
                "mode": run["mode"],
                "threshold": run["threshold"],
                "created_at": run["created_at"],
                "roc_auc": evaluation.get("roc_auc"),
                "pr_auc": evaluation.get("pr_auc"),
                "precision": evaluation.get("precision"),
                "recall": evaluation.get("recall"),
                "evaluation_scope": evaluation.get("scope"),
                "reference": metrics.get("reference"),
            },
            "level_counts": metrics["level_counts"],
            "risk_histogram": metrics["risk_histogram"],
            "ring_detection": metrics["ring_detection"],
            "graph": metrics["graph"],
            "group_importance": metrics["group_importance"],
            "notes": metrics.get("notes", []),
            "review_progress": {
                "suspected": len(suspected),
                "reviewed": len(reviewed),
                "confirmed": sum(1 for ring in reviewed if statuses[ring["ring_id"]]["status"] == "confirmed"),
                "dismissed": sum(1 for ring in reviewed if statuses[ring["ring_id"]]["status"] == "dismissed"),
            },
            "top_rings": [ring_row_public(ring, statuses) for ring in suspected[:6]],
            "top_customers": [customer_brief(row, feedback) for row in top_customers],
            "feedback": feedback_summary(dataset),
            "changes": metrics.get("changes"),
        }

    @app.get("/api/datasets/{dataset_id}/metrics")
    def metrics(dataset_id: str):
        dataset = require_results(dataset_id)
        runs = db.all("SELECT * FROM model_runs WHERE dataset_id = ? ORDER BY version", (dataset_id,))
        history = []
        for run in runs:
            run_metrics = run["metrics"]
            evaluation = run_metrics.get("evaluation") or {}
            history.append(
                {
                    "version": run["version"],
                    "created_at": run["created_at"],
                    "mode": run["mode"],
                    "threshold": run["threshold"],
                    "n_feedback": run["n_feedback"],
                    "feedback": run_metrics.get("feedback"),
                    "roc_auc": evaluation.get("roc_auc"),
                    "pr_auc": evaluation.get("pr_auc"),
                    "precision": evaluation.get("precision"),
                    "recall": evaluation.get("recall"),
                    "f1": evaluation.get("f1"),
                    "level_counts": run_metrics.get("level_counts"),
                    "n_suspected_rings": (run_metrics.get("ring_detection") or {}).get("n_suspected"),
                    "changes": run_metrics.get("changes"),
                    "evaluation_scope": evaluation.get("scope"),
                    "previous_same_customers": evaluation.get("previous_version"),
                }
            )
        current = next(run for run in runs if run["version"] == dataset["active_version"])
        return {"version": current["version"], "mode": current["mode"], "current": current["metrics"], "history": history}

    @app.get("/api/datasets/{dataset_id}/customers")
    def list_customers(
        dataset_id: str,
        q: str = "",
        level: Literal["high", "medium", "low", "all"] = "all",
        ring: str | None = None,
        reviewed: Literal["all", "fraud", "legit", "unreviewed"] = "all",
        sort: Literal["risk", "name", "degree", "customer_id"] = "risk",
        order: Literal["asc", "desc"] = "desc",
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        require_results(dataset_id)
        feedback = db.feedback_labels(dataset_id)
        where = ["dataset_id = ?"]
        params: list = [dataset_id]
        if q.strip():
            where.append("(customer_id LIKE ? OR name LIKE ?)")
            like = f"%{q.strip()}%"
            params += [like, like]
        if level != "all":
            where.append("risk_level = ?")
            params.append(level)
        if ring:
            where.append("ring_id = ?")
            params.append(ring)
        if reviewed != "all":
            wanted = {cid for cid, value in feedback.items() if (value == 1) == (reviewed == "fraud")}
            if reviewed == "unreviewed":
                if feedback:
                    where.append(f"customer_id NOT IN ({','.join('?' * len(feedback))})")
                    params += list(feedback)
            else:
                if not wanted:
                    return {"total": 0, "items": []}
                where.append(f"customer_id IN ({','.join('?' * len(wanted))})")
                params += list(wanted)
        column = {"risk": "risk", "name": "name", "degree": "degree", "customer_id": "customer_id"}[sort]
        direction = "DESC" if order == "desc" else "ASC"
        clause = " AND ".join(where)
        total = db.scalar(f"SELECT COUNT(*) FROM customers WHERE {clause}", tuple(params))
        rows = db.all(
            f"SELECT * FROM customers WHERE {clause} ORDER BY {column} {direction}, customer_id LIMIT ? OFFSET ?",
            tuple(params + [limit, offset]),
        )
        return {"total": total, "items": [customer_brief(row, feedback) for row in rows]}

    @app.get("/api/datasets/{dataset_id}/customers/{customer_id}")
    def customer_detail(dataset_id: str, customer_id: str):
        dataset = require_results(dataset_id)
        row = db.one("SELECT * FROM customers WHERE dataset_id = ? AND customer_id = ?", (dataset_id, customer_id))
        if row is None:
            raise HTTPException(404, "Customer not found.")
        feedback = db.feedback_labels(dataset_id)
        run = active_run(dataset)
        my_keys = {attribute["key"]: attribute for attribute in (row["attributes"] or [])}
        connections = []
        for link in neighbors(dataset_id, customer_id):
            other = db.one(
                "SELECT customer_id, name, risk, risk_level, ring_id, label, attributes_json FROM customers "
                "WHERE dataset_id = ? AND customer_id = ?",
                (dataset_id, link["other"]),
            )
            if other is None:
                continue
            shared = [
                {"type": attribute["type"], "value": attribute["value"]}
                for attribute in (other["attributes"] or [])
                if attribute["key"] in my_keys
            ]
            connections.append(
                {
                    "customer_id": other["customer_id"],
                    "name": other["name"],
                    "risk": other["risk"],
                    "risk_level": other["risk_level"],
                    "ring_id": other["ring_id"],
                    "label": other["label"],
                    "analyst_label": feedback.get(other["customer_id"]),
                    "types": link["types"].split(","),
                    "shared": shared,
                }
            )
        connections.sort(key=lambda item: -item["risk"])
        ring = None
        if row["ring_id"]:
            ring_row = db.one("SELECT * FROM rings WHERE dataset_id = ? AND ring_id = ?", (dataset_id, row["ring_id"]))
            if ring_row:
                ring = ring_row_public(ring_row, ring_statuses(dataset_id))
        events = db.all(
            "SELECT event_date, event_type, credit_limit, utilization FROM events "
            "WHERE dataset_id = ? AND customer_id = ? ORDER BY event_date LIMIT 1000",
            (dataset_id, customer_id),
        )
        reviews = [
            review
            for review in db.reviews(dataset_id)
            if (review["target_type"] == "customer" and review["target_id"] == customer_id)
            or (review["target_type"] == "ring" and customer_id in (review["members"] or []))
        ]
        return {
            "customer_id": row["customer_id"],
            "name": row["name"],
            "risk": row["risk"],
            "risk_level": row["risk_level"],
            "rank": row["rank"],
            "n_customers": (dataset["summary"] or {}).get("n_customers"),
            "threshold": run["threshold"],
            "mode": run["mode"],
            "label": row["label"],
            "truth_ring": row["truth_ring"],
            "open_date": row["open_date"],
            "analyst_label": feedback.get(customer_id),
            "degree": row["degree"],
            "high_neighbors": row["high_neighbors"],
            "features": row["features"],
            "feature_labels": run["metrics"].get("feature_labels", {}),
            "explanation": row["explanation"],
            "attributes": row["attributes"],
            "connections": connections,
            "ring": ring,
            "events": events,
            "reviews": [
                {
                    "id": review["id"],
                    "target_type": review["target_type"],
                    "target_id": review["target_id"],
                    "decision": review["decision"],
                    "note": review["note"],
                    "created_at": review["created_at"],
                    "included": customer_id in (review["included"] or []) if review["target_type"] == "ring" else True,
                }
                for review in reviews
            ],
        }

    @app.get("/api/datasets/{dataset_id}/customers/{customer_id}/graph")
    def customer_graph(dataset_id: str, customer_id: str, hops: int = Query(2, ge=1, le=3), max_nodes: int = Query(120, ge=10, le=500)):
        require_results(dataset_id)
        if db.one("SELECT 1 AS ok FROM customers WHERE dataset_id = ? AND customer_id = ?", (dataset_id, customer_id)) is None:
            raise HTTPException(404, "Customer not found.")
        distance = {customer_id: 0}
        queue = deque([customer_id])
        truncated = False
        while queue:
            node = queue.popleft()
            if distance[node] >= hops:
                continue
            for link in neighbors(dataset_id, node):
                other = link["other"]
                if other in distance:
                    continue
                if len(distance) >= max_nodes:
                    truncated = True
                    break
                distance[other] = distance[node] + 1
                queue.append(other)
        feedback = db.feedback_labels(dataset_id)
        payload = graph_payload(
            dataset_id, list(distance), feedback, {node: {"hop": hop} for node, hop in distance.items()}
        )
        payload["center"] = customer_id
        payload["truncated"] = truncated
        return payload

    @app.post("/api/datasets/{dataset_id}/customers/{customer_id}/review")
    def review_customer(dataset_id: str, customer_id: str, request: ReviewRequest):
        dataset = require_results(dataset_id)
        if db.one("SELECT 1 AS ok FROM customers WHERE dataset_id = ? AND customer_id = ?", (dataset_id, customer_id)) is None:
            raise HTTPException(404, "Customer not found.")
        db.add_review(dataset_id, "customer", customer_id, request.decision, request.note, [customer_id], [customer_id], dataset["active_version"])
        return {"analyst_label": db.feedback_labels(dataset_id).get(customer_id), "feedback": feedback_summary(dataset)}

    @app.get("/api/datasets/{dataset_id}/rings")
    def list_rings(
        dataset_id: str,
        status: Literal["all", "pending", "confirmed", "dismissed"] = "all",
        scope: Literal["suspected", "other", "all"] = "suspected",
        q: str = "",
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        require_results(dataset_id)
        statuses = ring_statuses(dataset_id)
        where = ["dataset_id = ?"]
        params: list = [dataset_id]
        if scope == "suspected":
            where.append("suspected = 1")
        elif scope == "other":
            where.append("suspected = 0")
        rows = db.all(
            f"SELECT * FROM rings WHERE {' AND '.join(where)} ORDER BY score DESC, size DESC, ring_id", tuple(params)
        )
        needle = q.strip().lower()
        if needle:
            member_hits = {
                row["ring_id"]
                for row in db.all(
                    "SELECT DISTINCT ring_id FROM customers WHERE dataset_id = ? AND ring_id IS NOT NULL "
                    "AND (lower(customer_id) LIKE ? OR lower(name) LIKE ?)",
                    (dataset_id, f"%{needle}%", f"%{needle}%"),
                )
            }
            rows = [row for row in rows if needle in row["ring_id"].lower() or row["ring_id"] in member_hits]
        items = [ring_row_public(row, statuses) for row in rows]
        counts = {"all": len(items), "pending": 0, "confirmed": 0, "dismissed": 0}
        for item in items:
            counts[item["status"]] += 1
        if status != "all":
            items = [item for item in items if item["status"] == status]
        return {"total": len(items), "counts": counts, "items": items[offset : offset + limit]}

    @app.get("/api/datasets/{dataset_id}/rings/{ring_id}")
    def ring_detail(dataset_id: str, ring_id: str):
        dataset = require_results(dataset_id)
        row = db.one("SELECT * FROM rings WHERE dataset_id = ? AND ring_id = ?", (dataset_id, ring_id))
        if row is None:
            raise HTTPException(404, "Ring not found.")
        run = active_run(dataset)
        threshold = run["threshold"]
        feedback = db.feedback_labels(dataset_id)
        statuses = ring_statuses(dataset_id)
        members = row["members"]
        member_rows = {
            item["customer_id"]: item
            for item in db.all(
                f"SELECT * FROM customers WHERE dataset_id = ? AND customer_id IN ({','.join('?' * len(members))})",
                (dataset_id, *members),
            )
        }
        latest = db.review_status(dataset_id).get(("ring", ring_id))
        member_items = []
        for customer in members:
            item = member_rows[customer]
            brief = customer_brief(item, feedback)
            brief["suggested"] = item["risk"] >= threshold / 2
            brief["open_date"] = item["open_date"]
            brief["attributes"] = item["attributes"]
            member_items.append(brief)
        if not any(item["suggested"] for item in member_items):
            for item in member_items:
                item["suggested"] = True
        # Outside accounts directly linked to the ring, for context in the graph.
        outside: dict[str, int] = {}
        for customer in members:
            for link in neighbors(dataset_id, customer):
                if link["other"] not in member_rows:
                    outside[link["other"]] = outside.get(link["other"], 0) + 1
        outside_ids = sorted(outside, key=lambda node: -outside[node])[:40]
        extra = {customer: {"member": True} for customer in members}
        extra.update({customer: {"member": False} for customer in outside_ids})
        graph = graph_payload(dataset_id, members + outside_ids, feedback, extra)
        history = [
            {
                "id": review["id"],
                "decision": review["decision"],
                "note": review["note"],
                "created_at": review["created_at"],
                "included": review["included"],
                "model_version": review["model_version"],
            }
            for review in db.reviews(dataset_id)
            if review["target_type"] == "ring" and review["target_id"] == ring_id
        ]
        ordered = db.all(
            "SELECT ring_id FROM rings WHERE dataset_id = ? AND suspected = ? ORDER BY score DESC, size DESC, ring_id",
            (dataset_id, row["suspected"]),
        )
        ids = [item["ring_id"] for item in ordered]
        position = ids.index(ring_id)
        return {
            **ring_row_public(row, statuses),
            "evidence": row["evidence"],
            "members": member_items,
            "graph": graph,
            "threshold": threshold,
            "history": history,
            "included": latest["included"] if latest and latest["decision"] != "reset" else None,
            "previous_ring": ids[position - 1] if position > 0 else None,
            "next_ring": ids[position + 1] if position + 1 < len(ids) else None,
        }

    @app.post("/api/datasets/{dataset_id}/rings/{ring_id}/review")
    def review_ring(dataset_id: str, ring_id: str, request: ReviewRequest):
        dataset = require_results(dataset_id)
        row = db.one("SELECT * FROM rings WHERE dataset_id = ? AND ring_id = ?", (dataset_id, ring_id))
        if row is None:
            raise HTTPException(404, "Ring not found.")
        members = row["members"]
        if request.include is None:
            if request.decision == "confirm":
                run = active_run(dataset)
                risks = dict(
                    (item["customer_id"], item["risk"])
                    for item in db.all(
                        f"SELECT customer_id, risk FROM customers WHERE dataset_id = ? AND customer_id IN ({','.join('?' * len(members))})",
                        (dataset_id, *members),
                    )
                )
                include = [customer for customer in members if risks.get(customer, 0) >= run["threshold"] / 2] or list(members)
            else:
                include = list(members)
        else:
            unknown = set(request.include) - set(members)
            if unknown:
                raise HTTPException(400, "Only ring members can be included in a review.")
            include = [customer for customer in members if customer in set(request.include)]
            if request.decision != "reset" and not include:
                raise HTTPException(400, "Select at least one member.")
        db.add_review(dataset_id, "ring", ring_id, request.decision, request.note, members, include, dataset["active_version"])
        status = ring_statuses(dataset_id).get(ring_id, {"status": "pending"})
        return {"ring_id": ring_id, "status": status["status"], "included": include, "feedback": feedback_summary(dataset)}

    @app.get("/api/datasets/{dataset_id}/graph")
    def network(
        dataset_id: str,
        scope: Literal["suspected", "all"] = "suspected",
        min_score: float = Query(0.0, ge=0, le=1),
        types: str = "",
        status: Literal["all", "pending", "confirmed", "dismissed"] = "all",
        max_nodes: int = Query(settings.MAX_GRAPH_NODES, ge=10, le=5000),
    ):
        require_results(dataset_id)
        statuses = ring_statuses(dataset_id)
        where = "dataset_id = ? AND score >= ?" + (" AND suspected = 1" if scope == "suspected" else "")
        rings = db.all(
            f"SELECT ring_id, size, members_json, suspected, score FROM rings WHERE {where} ORDER BY score DESC, size DESC",
            (dataset_id, min_score),
        )
        if status != "all":
            rings = [ring for ring in rings if statuses.get(ring["ring_id"], {}).get("status", "pending") == status]
        wanted_types = {kind for kind in types.split(",") if kind}
        nodes: list[str] = []
        included_rings = 0
        truncated = False
        for ring in rings:
            if len(nodes) + ring["size"] > max_nodes:
                truncated = True
                break
            nodes.extend(ring["members"])
            included_rings += 1
        feedback = db.feedback_labels(dataset_id)
        payload = graph_payload(dataset_id, nodes, feedback)
        if wanted_types:
            payload["edges"] = [edge for edge in payload["edges"] if wanted_types & set(edge["types"])]
            connected = {edge["source"] for edge in payload["edges"]} | {edge["target"] for edge in payload["edges"]}
            payload["nodes"] = [node for node in payload["nodes"] if node["id"] in connected]
        ring_info = {
            ring["ring_id"]: {
                "suspected": bool(ring["suspected"]),
                "score": ring["score"],
                "status": statuses.get(ring["ring_id"], {}).get("status", "pending"),
            }
            for ring in rings[:included_rings]
        }
        payload.update(
            {
                "rings": ring_info,
                "truncated": truncated,
                "n_rings_total": len(rings),
                "n_rings_shown": included_rings,
            }
        )
        return payload

    @app.get("/api/datasets/{dataset_id}/export/customers.csv")
    def export_customers(dataset_id: str):
        require_results(dataset_id)
        feedback = db.feedback_labels(dataset_id)
        rows = db.all(
            "SELECT customer_id, name, risk, risk_level, rank, ring_id, degree, top_reason, explanation_json "
            "FROM customers WHERE dataset_id = ? ORDER BY rank",
            (dataset_id,),
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["customer_id", "name", "risk_score", "risk_level", "rank", "ring_id", "linked_accounts", "analyst_label", "explanation"])
        for row in rows:
            label = feedback.get(row["customer_id"])
            writer.writerow(
                [
                    row["customer_id"],
                    row["name"],
                    round(row["risk"] * 100, 1),
                    row["risk_level"],
                    row["rank"],
                    row["ring_id"] or "",
                    row["degree"],
                    "" if label is None else ("fraud" if label == 1 else "legitimate"),
                    row["explanation"]["summary"],
                ]
            )
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="risk_scores_{dataset_id}.csv"'},
        )

    # ------------------------------------------------------------------
    # Sample data and frontend
    # ------------------------------------------------------------------

    def sample_files() -> list[dict]:
        if not settings.SAMPLE_DATA_DIR.is_dir():
            return []
        descriptions = {}
        index = settings.SAMPLE_DATA_DIR / "index.json"
        if index.is_file():
            descriptions = json.loads(index.read_text(encoding="utf-8"))
        return [
            {"name": path.name, "bytes": path.stat().st_size, "description": descriptions.get(path.name, "")}
            for path in sorted(settings.SAMPLE_DATA_DIR.glob("*.csv"))
        ]

    @app.get("/api/sample-data")
    def list_samples():
        return sample_files()

    @app.get("/api/sample-data/{name}")
    def download_sample(name: str):
        if name not in {item["name"] for item in sample_files()}:
            raise HTTPException(404, "Sample file not found.")
        return FileResponse(settings.SAMPLE_DATA_DIR / name, media_type="text/csv", filename=name)

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def api_not_found(rest: str):
        return JSONResponse({"detail": "Not found."}, status_code=404)

    @app.get("/{rest:path}", include_in_schema=False)
    def frontend(rest: str):
        dist = settings.FRONTEND_DIST
        index = dist / "index.html"
        if not index.is_file():
            return HTMLResponse(
                "<h1>Frontend not built</h1><p>Run <code>npm install</code> and <code>npm run build</code> "
                "in the <code>frontend</code> folder, or start the dev server with <code>npm run dev</code> "
                "and open <a href='http://localhost:5173'>http://localhost:5173</a>. "
                "The API is available under <a href='/docs'>/docs</a>.</p>",
                status_code=200,
            )
        candidate = (dist / rest).resolve()
        if rest and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)

    return app


_default_app: FastAPI | None = None


def __getattr__(name: str):
    """Create the default app lazily (``uvicorn backend.main:app``).

    Importing this module has no side effects, so tests can build their own
    app with ``create_app(tmp_dir)`` without touching ``storage/``.
    """
    global _default_app
    if name == "app":
        if _default_app is None:
            _default_app = create_app()
        return _default_app
    raise AttributeError(name)
