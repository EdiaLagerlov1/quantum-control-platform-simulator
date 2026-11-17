"""Test doubles and helpers shared by the API tests."""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quantum_platform.hardware import (
    ExecutionResult,
    ExperimentSpec,
    HardwareAdapter,
    HardwareError,
    HardwareJobStatus,
)

TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}


class FakeHardwareAdapter(HardwareAdapter):
    """A hardware backend the test controls.

    It implements the same contract as the real adapters, but does no physics:

    - ``counts``: what the next run returns. ``None`` means "all shots measured as zeros".
    - ``fail_with``: if set, every run raises this error instead of returning a result.
    - ``executed`` / ``cancelled``: a record of what the server asked the hardware to do.
    """

    def __init__(self) -> None:
        self.counts: dict[str, int] | None = None
        self.fail_with: HardwareError | None = None
        self.executed: list[ExperimentSpec] = []
        self.cancelled: list[str] = []
        self._statuses: dict[str, HardwareJobStatus] = {}

    async def execute(self, experiment: ExperimentSpec) -> ExecutionResult:
        self.executed.append(experiment)
        if self.fail_with is not None:
            self._statuses[experiment.job_id] = HardwareJobStatus.FAILED
            raise self.fail_with
        counts = self.counts
        if counts is None:
            counts = {"0" * experiment.qubits: experiment.shots}
        self._statuses[experiment.job_id] = HardwareJobStatus.COMPLETED
        return ExecutionResult(
            job_id=experiment.job_id, counts=dict(counts), shots=experiment.shots, duration_ms=1.0
        )

    async def cancel(self, job_id: str) -> None:
        self.cancelled.append(job_id)
        if self._statuses.get(job_id) is HardwareJobStatus.RUNNING:
            self._statuses[job_id] = HardwareJobStatus.CANCELLED

    async def get_status(self, job_id: str) -> HardwareJobStatus:
        return self._statuses.get(job_id, HardwareJobStatus.UNKNOWN)


def wait_until_terminal(
    client: TestClient, experiment_id: str, headers: dict[str, str], timeout: float = 5.0
) -> dict[str, Any]:
    """Poll the experiment until it reaches a terminal status and return its JSON body.

    The timeout is a ceiling, not a delay: the loop returns as soon as the experiment is done.
    """
    deadline = time.monotonic() + timeout
    status = "never fetched"
    while time.monotonic() < deadline:
        response = client.get(f"/v1/experiments/{experiment_id}", headers=headers)
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        status = body["status"]
        if status in TERMINAL_STATUSES:
            return body
        time.sleep(0.01)
    pytest.fail(f"experiment {experiment_id} was still {status} after {timeout}s")
