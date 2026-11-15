"""Execution service: queues jobs and runs them on the hardware adapter."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime

from quantum_platform.execution.queue import JobQueue
from quantum_platform.execution.states import JobStatus
from quantum_platform.hardware.base import (
    ExecutionResult,
    ExperimentSpec,
    GateSpec,
    HardwareAdapter,
    HardwareError,
)
from quantum_platform.logging_config import correlation_id_var
from quantum_platform.storage.base import ExperimentRecord, ExperimentRepository

logger = logging.getLogger(__name__)


def to_spec(record: ExperimentRecord) -> ExperimentSpec:
    return ExperimentSpec(
        job_id=record.id,
        qubits=record.qubits,
        shots=record.shots,
        gates=tuple(
            GateSpec(
                name=gate["name"],
                target=gate["target"],
                control=gate.get("control"),
                angle=gate.get("angle"),
            )
            for gate in record.gates
        ),
        seed=record.seed,
    )


class ExecutionService:
    def __init__(
        self,
        repo: ExperimentRepository,
        queue: JobQueue,
        adapter: HardwareAdapter,
        *,
        clock: Callable[[], datetime],
        job_timeout_s: float = 30.0,
        concurrency: int = 2,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        self._repo = repo
        self._queue = queue
        self._adapter = adapter
        self._clock = clock
        self._job_timeout_s = job_timeout_s
        self._concurrency = concurrency
        self._workers: list[asyncio.Task[None]] = []
        self._running: dict[str, asyncio.Task[ExecutionResult]] = {}

    @property
    def is_running(self) -> bool:
        return bool(self._workers) and all(not worker.done() for worker in self._workers)

    @property
    def queue_depth(self) -> int:
        return self._queue.depth()

    async def start(self) -> None:
        """Recover jobs left over from a previous process, then start the workers."""
        if self._workers:
            return
        for record in self._repo.list_by_status(JobStatus.RUNNING):
            self._repo.transition(
                record.id,
                {JobStatus.RUNNING},
                JobStatus.FAILED,
                self._clock(),
                error_code="worker_interrupted",
                error_message="The worker stopped while this experiment was running.",
            )
        for record in self._repo.list_by_status(JobStatus.QUEUED):
            await self._queue.enqueue(record.id)
        self._workers = [
            asyncio.create_task(self._work(), name=f"worker-{index}")
            for index in range(self._concurrency)
        ]

    async def stop(self) -> None:
        workers, self._workers = self._workers, []
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    async def submit(self, job_id: str, correlation_id: str | None = None) -> bool:
        """Queue a CREATED experiment. Returns ``False`` if it was not in CREATED."""
        moved = self._repo.transition(
            job_id,
            {JobStatus.CREATED},
            JobStatus.QUEUED,
            self._clock(),
            correlation_id=correlation_id,
        )
        if moved:
            await self._queue.enqueue(job_id)
            logger.info("job queued", extra={"job_id": job_id, "queue_depth": self.queue_depth})
        return moved

    async def cancel(self, job_id: str) -> bool:
        """Cancel a QUEUED or RUNNING experiment. Returns ``False`` for any other state."""
        moved = self._repo.transition(
            job_id, {JobStatus.QUEUED, JobStatus.RUNNING}, JobStatus.CANCELLED, self._clock()
        )
        if not moved:
            return False
        task = self._running.get(job_id)
        if task is not None:
            task.cancel()
            await self._adapter.cancel(job_id)
        logger.info("job cancelled", extra={"job_id": job_id})
        return True

    async def _work(self) -> None:
        while True:
            job_id = await self._queue.dequeue()
            try:
                await self._process(job_id)
            except Exception:
                logger.exception("worker failed to process job", extra={"job_id": job_id})

    async def _process(self, job_id: str) -> None:
        if not self._repo.transition(job_id, {JobStatus.QUEUED}, JobStatus.RUNNING, self._clock()):
            logger.info("job skipped: no longer queued", extra={"job_id": job_id})
            return
        record = self._repo.get(job_id)
        if record is None:
            return
        token = correlation_id_var.set(record.correlation_id)
        try:
            await self._execute(record)
        finally:
            self._running.pop(job_id, None)
            correlation_id_var.reset(token)

    async def _execute(self, record: ExperimentRecord) -> None:
        job_id = record.id
        logger.info("job started", extra={"job_id": job_id})
        task = asyncio.create_task(self._adapter.execute(to_spec(record)))
        self._running[job_id] = task
        try:
            result = await asyncio.wait_for(task, timeout=self._job_timeout_s)
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise  # the worker itself is shutting down
            logger.info("job execution stopped after cancellation", extra={"job_id": job_id})
            return
        except TimeoutError:
            await self._adapter.cancel(job_id)
            self._fail(
                job_id,
                JobStatus.TIMED_OUT,
                "execution_timeout",
                f"Execution exceeded {self._job_timeout_s}s.",
            )
            return
        except HardwareError as exc:
            self._fail(job_id, JobStatus.FAILED, exc.code, str(exc) or exc.code)
            return
        except Exception as exc:
            logger.exception("unexpected adapter error", extra={"job_id": job_id})
            self._fail(job_id, JobStatus.FAILED, "internal_error", type(exc).__name__)
            return

        if result.shots != record.shots or sum(result.counts.values()) != record.shots:
            self._fail(
                job_id,
                JobStatus.FAILED,
                "malformed_result",
                "Hardware returned counts that do not match the requested shots.",
            )
            return
        stored = self._repo.complete(job_id, result.counts, result.duration_ms, self._clock())
        if stored:
            logger.info(
                "job completed", extra={"job_id": job_id, "duration_ms": result.duration_ms}
            )
        else:
            logger.info("result discarded: job no longer running", extra={"job_id": job_id})

    def _fail(self, job_id: str, status: JobStatus, code: str, message: str) -> None:
        moved = self._repo.transition(
            job_id,
            {JobStatus.RUNNING},
            status,
            self._clock(),
            error_code=code,
            error_message=message,
        )
        logger.warning(
            "job failed",
            extra={"job_id": job_id, "status": status.value, "error_code": code, "applied": moved},
        )
