"""SQLite implementation of the experiment repository."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Collection
from datetime import datetime

from quantum_platform.execution.states import JobStatus, can_transition
from quantum_platform.storage.base import ExperimentRecord, ExperimentRepository

_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    name TEXT NOT NULL,
    qubits INTEGER NOT NULL,
    shots INTEGER NOT NULL,
    gates TEXT NOT NULL,
    seed INTEGER,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    correlation_id TEXT,
    error_code TEXT,
    error_message TEXT,
    counts TEXT,
    duration_ms REAL
);
CREATE INDEX IF NOT EXISTS idx_experiments_owner ON experiments (owner, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments (status);
"""

_COLUMNS = (
    "id, owner, name, qubits, shots, gates, seed, status, created_at, updated_at, "
    "correlation_id, error_code, error_message, counts, duration_ms"
)


def _to_record(row: sqlite3.Row) -> ExperimentRecord:
    return ExperimentRecord(
        id=row["id"],
        owner=row["owner"],
        name=row["name"],
        qubits=row["qubits"],
        shots=row["shots"],
        gates=json.loads(row["gates"]),
        seed=row["seed"],
        status=JobStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        correlation_id=row["correlation_id"],
        error_code=row["error_code"],
        error_message=row["error_message"],
        counts=json.loads(row["counts"]) if row["counts"] is not None else None,
        duration_ms=row["duration_ms"],
    )


class SqliteExperimentRepository(ExperimentRepository):
    """Stores experiments in one SQLite database. Use ``":memory:"`` for a throwaway store."""

    def __init__(self, path: str = ":memory:") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def create(self, record: ExperimentRecord) -> None:
        with self._lock:
            self._conn.execute(
                f"INSERT INTO experiments ({_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    record.id,
                    record.owner,
                    record.name,
                    record.qubits,
                    record.shots,
                    json.dumps(record.gates),
                    record.seed,
                    record.status.value,
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                    record.correlation_id,
                    record.error_code,
                    record.error_message,
                    json.dumps(record.counts) if record.counts is not None else None,
                    record.duration_ms,
                ),
            )

    def get(self, experiment_id: str) -> ExperimentRecord | None:
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_COLUMNS} FROM experiments WHERE id = ?", (experiment_id,)
            ).fetchone()
        return _to_record(row) if row is not None else None

    def list_for_owner(
        self, owner: str, limit: int, offset: int
    ) -> tuple[list[ExperimentRecord], int]:
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {_COLUMNS} FROM experiments WHERE owner = ? "
                "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                (owner, limit, offset),
            ).fetchall()
            total = self._conn.execute(
                "SELECT COUNT(*) FROM experiments WHERE owner = ?", (owner,)
            ).fetchone()[0]
        return [_to_record(row) for row in rows], int(total)

    def list_by_status(self, status: JobStatus) -> list[ExperimentRecord]:
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {_COLUMNS} FROM experiments WHERE status = ? ORDER BY created_at, id",
                (status.value,),
            ).fetchall()
        return [_to_record(row) for row in rows]

    def transition(
        self,
        experiment_id: str,
        expected: Collection[JobStatus],
        target: JobStatus,
        now: datetime,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
        correlation_id: str | None = None,
    ) -> bool:
        for source in expected:
            if not can_transition(source, target):
                raise ValueError(f"illegal transition {source} -> {target}")
        placeholders = ",".join("?" * len(expected))
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE experiments SET status = ?, updated_at = ?, error_code = ?, "
                "error_message = ?, correlation_id = COALESCE(?, correlation_id) "
                f"WHERE id = ? AND status IN ({placeholders})",
                (
                    target.value,
                    now.isoformat(),
                    error_code,
                    error_message,
                    correlation_id,
                    experiment_id,
                    *(status.value for status in expected),
                ),
            )
        return cursor.rowcount == 1

    def complete(
        self, experiment_id: str, counts: dict[str, int], duration_ms: float, now: datetime
    ) -> bool:
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE experiments SET status = ?, updated_at = ?, counts = ?, duration_ms = ? "
                "WHERE id = ? AND status = ?",
                (
                    JobStatus.COMPLETED.value,
                    now.isoformat(),
                    json.dumps(counts),
                    duration_ms,
                    experiment_id,
                    JobStatus.RUNNING.value,
                ),
            )
        return cursor.rowcount == 1

    def ping(self) -> bool:
        try:
            with self._lock:
                self._conn.execute("SELECT 1").fetchone()
        except sqlite3.Error:
            return False
        return True

    def close(self) -> None:
        with self._lock:
            self._conn.close()
