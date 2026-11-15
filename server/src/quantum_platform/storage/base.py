"""Persistence abstraction for experiments."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from quantum_platform.execution.states import JobStatus


@dataclass
class ExperimentRecord:
    id: str
    owner: str
    name: str
    qubits: int
    shots: int
    gates: list[dict[str, Any]]
    seed: int | None
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    correlation_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    counts: dict[str, int] | None = None
    duration_ms: float | None = None


class ExperimentRepository(ABC):
    @abstractmethod
    def create(self, record: ExperimentRecord) -> None: ...

    @abstractmethod
    def get(self, experiment_id: str) -> ExperimentRecord | None: ...

    @abstractmethod
    def list_for_owner(
        self, owner: str, limit: int, offset: int
    ) -> tuple[list[ExperimentRecord], int]:
        """Return one page of the owner's experiments, newest first, and the total count."""

    @abstractmethod
    def list_by_status(self, status: JobStatus) -> list[ExperimentRecord]: ...

    @abstractmethod
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
        """Atomically move the experiment to ``target`` if its status is in ``expected``.

        Returns ``False`` and changes nothing when the current status is not expected.
        Raises ``ValueError`` if any ``expected -> target`` pair is not a legal transition.
        """

    @abstractmethod
    def complete(
        self, experiment_id: str, counts: dict[str, int], duration_ms: float, now: datetime
    ) -> bool:
        """Atomically store the result and move RUNNING to COMPLETED.

        Returns ``False`` and stores nothing if the experiment is no longer RUNNING.
        """

    @abstractmethod
    def ping(self) -> bool:
        """Whether the store is reachable."""

    @abstractmethod
    def close(self) -> None: ...
