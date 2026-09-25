"""SQLite persistence for datasets, jobs, scores, rings and analyst reviews."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    mapping_json TEXT,
    files_json TEXT,
    summary_json TEXT,
    active_version INTEGER NOT NULL DEFAULT 0,
    error TEXT
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    dataset_id TEXT,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0,
    stage TEXT,
    message TEXT,
    stages_json TEXT,
    params_json TEXT,
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS model_runs (
    dataset_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    job_id TEXT,
    created_at TEXT NOT NULL,
    mode TEXT NOT NULL,
    threshold REAL NOT NULL,
    n_feedback INTEGER NOT NULL DEFAULT 0,
    metrics_json TEXT,
    PRIMARY KEY (dataset_id, version)
);
CREATE TABLE IF NOT EXISTS customers (
    dataset_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    name TEXT,
    label INTEGER,
    truth_ring TEXT,
    open_date TEXT,
    risk REAL NOT NULL,
    risk_level TEXT NOT NULL,
    rank INTEGER NOT NULL,
    ring_id TEXT,
    degree INTEGER NOT NULL DEFAULT 0,
    high_neighbors INTEGER NOT NULL DEFAULT 0,
    top_reason TEXT,
    features_json TEXT,
    explanation_json TEXT,
    attributes_json TEXT,
    PRIMARY KEY (dataset_id, customer_id)
);
CREATE INDEX IF NOT EXISTS customers_by_risk ON customers (dataset_id, risk DESC);
CREATE INDEX IF NOT EXISTS customers_by_ring ON customers (dataset_id, ring_id);
CREATE TABLE IF NOT EXISTS edges (
    dataset_id TEXT NOT NULL,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    types TEXT NOT NULL,
    weight INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS edges_by_source ON edges (dataset_id, source);
CREATE INDEX IF NOT EXISTS edges_by_target ON edges (dataset_id, target);
CREATE TABLE IF NOT EXISTS rings (
    dataset_id TEXT NOT NULL,
    ring_id TEXT NOT NULL,
    size INTEGER NOT NULL,
    n_edges INTEGER NOT NULL,
    density REAL NOT NULL,
    score REAL NOT NULL,
    max_risk REAL NOT NULL,
    n_high INTEGER NOT NULL,
    suspected INTEGER NOT NULL,
    shared_types_json TEXT,
    evidence_json TEXT,
    explanation TEXT,
    truth_json TEXT,
    members_json TEXT,
    open_span_days INTEGER,
    PRIMARY KEY (dataset_id, ring_id)
);
CREATE INDEX IF NOT EXISTS rings_by_score ON rings (dataset_id, suspected, score DESC);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    note TEXT,
    members_json TEXT,
    included_json TEXT,
    created_at TEXT NOT NULL,
    model_version INTEGER
);
CREATE INDEX IF NOT EXISTS reviews_by_target ON reviews (dataset_id, target_type, target_id);
CREATE TABLE IF NOT EXISTS events (
    dataset_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    event_date TEXT NOT NULL,
    event_type TEXT,
    credit_limit REAL,
    utilization REAL
);
CREATE INDEX IF NOT EXISTS events_by_customer ON events (dataset_id, customer_id);
"""

JSON_COLUMNS = {
    "mapping_json",
    "files_json",
    "summary_json",
    "stages_json",
    "params_json",
    "result_json",
    "metrics_json",
    "features_json",
    "explanation_json",
    "attributes_json",
    "shared_types_json",
    "evidence_json",
    "truth_json",
    "members_json",
    "included_json",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dumps(value: Any) -> str:
    return json.dumps(value, default=_json_default, separators=(",", ":"))


def _json_default(value: Any):
    import numpy as np

    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.bool_,)):
        return bool(value)
    raise TypeError(f"Not JSON serialisable: {type(value).__name__}")


def decode_row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    result = {}
    for key in row.keys():
        value = row[key]
        if key in JSON_COLUMNS:
            result[key.removesuffix("_json")] = json.loads(value) if value else None
        else:
            result[key] = value
    return result


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """Serialise writers inside this process (SQLite allows one at a time)."""
        with self._write_lock, self.connect() as connection:
            yield connection

    def one(self, sql: str, params: tuple | dict = ()) -> dict | None:
        with self.connect() as connection:
            return decode_row(connection.execute(sql, params).fetchone())

    def all(self, sql: str, params: tuple | dict = ()) -> list[dict]:
        with self.connect() as connection:
            return [decode_row(row) for row in connection.execute(sql, params).fetchall()]

    def scalar(self, sql: str, params: tuple | dict = ()):
        with self.connect() as connection:
            row = connection.execute(sql, params).fetchone()
            return None if row is None else row[0]

    def execute(self, sql: str, params: tuple | dict = ()) -> int:
        with self.write() as connection:
            cursor = connection.execute(sql, params)
            return cursor.lastrowid

    # ------------------------------------------------------------------
    # Datasets
    # ------------------------------------------------------------------

    def create_dataset(self, dataset_id: str, name: str, source: str, mapping: dict | None, files: dict | None) -> None:
        self.execute(
            "INSERT INTO datasets (id, name, source, created_at, status, mapping_json, files_json) "
            "VALUES (?, ?, ?, ?, 'processing', ?, ?)",
            (dataset_id, name, source, utcnow(), dumps(mapping), dumps(files)),
        )

    def get_dataset(self, dataset_id: str) -> dict | None:
        return self.one("SELECT * FROM datasets WHERE id = ?", (dataset_id,))

    def list_datasets(self) -> list[dict]:
        return self.all("SELECT * FROM datasets ORDER BY created_at DESC, rowid DESC")

    def update_dataset(self, dataset_id: str, **fields) -> None:
        if not fields:
            return
        columns = []
        values = []
        for key, value in fields.items():
            column = f"{key}_json" if f"{key}_json" in JSON_COLUMNS else key
            columns.append(f"{column} = ?")
            values.append(dumps(value) if column in JSON_COLUMNS else value)
        values.append(dataset_id)
        self.execute(f"UPDATE datasets SET {', '.join(columns)} WHERE id = ?", tuple(values))

    def delete_dataset(self, dataset_id: str) -> None:
        with self.write() as connection:
            for table in ["customers", "edges", "rings", "reviews", "events", "model_runs"]:
                connection.execute(f"DELETE FROM {table} WHERE dataset_id = ?", (dataset_id,))
            connection.execute("DELETE FROM jobs WHERE dataset_id = ?", (dataset_id,))
            connection.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    def create_job(self, job_id: str, dataset_id: str | None, kind: str, stages: list[dict], params: dict) -> None:
        self.execute(
            "INSERT INTO jobs (id, dataset_id, kind, status, progress, stage, message, stages_json, params_json, created_at) "
            "VALUES (?, ?, ?, 'queued', 0, NULL, 'Waiting to start', ?, ?, ?)",
            (job_id, dataset_id, kind, dumps(stages), dumps(params), utcnow()),
        )

    def update_job(self, job_id: str, **fields) -> None:
        if not fields:
            return
        columns = []
        values = []
        for key, value in fields.items():
            column = f"{key}_json" if f"{key}_json" in JSON_COLUMNS else key
            columns.append(f"{column} = ?")
            values.append(dumps(value) if column in JSON_COLUMNS else value)
        values.append(job_id)
        self.execute(f"UPDATE jobs SET {', '.join(columns)} WHERE id = ?", tuple(values))

    def get_job(self, job_id: str) -> dict | None:
        return self.one("SELECT * FROM jobs WHERE id = ?", (job_id,))

    def list_jobs(self, dataset_id: str | None = None, limit: int = 50) -> list[dict]:
        if dataset_id:
            return self.all(
                "SELECT * FROM jobs WHERE dataset_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (dataset_id, limit),
            )
        return self.all("SELECT * FROM jobs ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,))

    def fail_interrupted_jobs(self) -> None:
        now = utcnow()
        with self.write() as connection:
            connection.execute(
                "UPDATE jobs SET status = 'failed', error = 'The server restarted while this job was running.', "
                "finished_at = ? WHERE status IN ('queued', 'running')",
                (now,),
            )
            connection.execute(
                "UPDATE datasets SET status = CASE WHEN active_version > 0 THEN 'ready' ELSE 'failed' END, "
                "error = CASE WHEN active_version > 0 THEN error ELSE 'Processing was interrupted.' END "
                "WHERE status = 'processing'"
            )

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------

    def add_review(
        self,
        dataset_id: str,
        target_type: str,
        target_id: str,
        decision: str,
        note: str,
        members: list[str],
        included: list[str],
        model_version: int,
    ) -> int:
        return self.execute(
            "INSERT INTO reviews (dataset_id, target_type, target_id, decision, note, members_json, included_json, "
            "created_at, model_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (dataset_id, target_type, target_id, decision, note, dumps(members), dumps(included), utcnow(), model_version),
        )

    def reviews(self, dataset_id: str) -> list[dict]:
        return self.all("SELECT * FROM reviews WHERE dataset_id = ? ORDER BY id", (dataset_id,))

    def feedback_labels(self, dataset_id: str) -> dict[str, int]:
        """Analyst labels per customer; the latest decision wins.

        A ring confirmation labels its included members as fraud and clears
        any earlier label on excluded members. A ring dismissal labels the
        included members legitimate. ``reset`` clears labels.
        """
        labels: dict[str, int] = {}
        for review in self.reviews(dataset_id):
            members = review["members"] or []
            included = set(review["included"] or [])
            decision = review["decision"]
            if review["target_type"] == "customer":
                customer = review["target_id"]
                if decision == "confirm":
                    labels[customer] = 1
                elif decision == "dismiss":
                    labels[customer] = 0
                else:
                    labels.pop(customer, None)
                continue
            for customer in members:
                if decision == "reset" or customer not in included:
                    labels.pop(customer, None)
                else:
                    labels[customer] = 1 if decision == "confirm" else 0
        return labels

    def review_status(self, dataset_id: str) -> dict[tuple[str, str], dict]:
        """Latest review per (target_type, target_id)."""
        latest: dict[tuple[str, str], dict] = {}
        for review in self.reviews(dataset_id):
            latest[(review["target_type"], review["target_id"])] = review
        return latest
