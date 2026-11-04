"""Durable SQLite storage for background job snapshots.

Results must survive server restarts and stay reachable through their
bookmarkable link for the retention period (default 14 days). Each job is
stored as one JSON document keyed by (kind, job_id). Process-local objects such
as cancellation events and resolver callables are never persisted.

Configuration (environment variables):
    KLINKPPI_JOB_DB              SQLite path, or ":memory:" (tests). Default:
                                 Data/jobs/klinkppi_jobs.sqlite3
    KLINKPPI_RESULT_RETENTION_DAYS  Days a finished result is kept. Default: 14
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from time import time

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = PROJECT_ROOT / "Data" / "jobs" / "klinkppi_jobs.sqlite3"


def retention_seconds() -> float:
    try:
        days = float(os.environ.get("KLINKPPI_RESULT_RETENTION_DAYS", "14"))
    except ValueError:
        days = 14.0
    return max(1.0, days) * 86400


class JobStore:
    def __init__(self, path: str | os.PathLike | None = None):
        configured = path if path is not None else os.environ.get("KLINKPPI_JOB_DB", str(DEFAULT_PATH))
        self.path = str(configured)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        if self.path != ":memory:":
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
                   kind TEXT NOT NULL,
                   job_id TEXT NOT NULL,
                   status TEXT NOT NULL,
                   created_at REAL NOT NULL,
                   updated_at REAL NOT NULL,
                   pinned INTEGER NOT NULL DEFAULT 0,
                   data TEXT NOT NULL,
                   PRIMARY KEY (kind, job_id))"""
        )
        self._connection.execute("CREATE INDEX IF NOT EXISTS jobs_expiry ON jobs (kind, pinned, created_at)")

    def save(self, kind: str, job: dict, *, pinned: bool = False) -> None:
        payload = json.dumps(job, separators=(",", ":"), default=str)
        with self._lock:
            self._connection.execute(
                """INSERT INTO jobs (kind, job_id, status, created_at, updated_at, pinned, data)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(kind, job_id) DO UPDATE SET
                       status=excluded.status, created_at=excluded.created_at,
                       updated_at=excluded.updated_at, pinned=excluded.pinned, data=excluded.data""",
                (kind, job["job_id"], str(job.get("status", "")), float(job.get("created_at") or time()),
                 time(), int(pinned), payload),
            )

    def load(self, kind: str, job_id: str) -> dict | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT data FROM jobs WHERE kind=? AND job_id=?", (kind, job_id)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def load_by_status(self, kind: str, statuses: set[str]) -> list[dict]:
        if not statuses:
            return []
        marks = ",".join("?" for _ in statuses)
        with self._lock:
            rows = self._connection.execute(
                f"SELECT data FROM jobs WHERE kind=? AND status IN ({marks})", (kind, *sorted(statuses))
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def delete(self, kind: str, job_id: str) -> None:
        with self._lock:
            self._connection.execute("DELETE FROM jobs WHERE kind=? AND job_id=?", (kind, job_id))

    def purge(self, kind: str, older_than: float, keep_statuses: set[str] = frozenset()) -> int:
        """Delete unpinned jobs created before ``older_than`` (epoch seconds)."""
        marks = ",".join("?" for _ in keep_statuses)
        status_clause = f" AND status NOT IN ({marks})" if keep_statuses else ""
        with self._lock:
            cursor = self._connection.execute(
                f"DELETE FROM jobs WHERE kind=? AND pinned=0 AND created_at < ?{status_clause}",
                (kind, older_than, *sorted(keep_statuses)),
            )
        return cursor.rowcount

    def count(self, kind: str) -> int:
        with self._lock:
            return self._connection.execute("SELECT COUNT(*) FROM jobs WHERE kind=?", (kind,)).fetchone()[0]


_STORE: JobStore | None = None
_STORE_LOCK = threading.Lock()


def get_store() -> JobStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = JobStore()
        return _STORE


def set_store(store: JobStore | None) -> None:
    """Replace the process store (tests use an in-memory database)."""
    global _STORE
    with _STORE_LOCK:
        _STORE = store
