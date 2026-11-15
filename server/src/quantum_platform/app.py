"""Application factory. Every collaborator can be replaced by the caller."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from quantum_platform import API_VERSION
from quantum_platform.api.deps import AppContext
from quantum_platform.api.errors import install_error_handlers
from quantum_platform.api.middleware import install_request_context
from quantum_platform.api.routes import ops_router, router
from quantum_platform.execution.queue import InMemoryJobQueue, JobQueue
from quantum_platform.execution.service import ExecutionService
from quantum_platform.hardware.base import HardwareAdapter
from quantum_platform.hardware.simulator import SimulatorAdapter
from quantum_platform.settings import Settings
from quantum_platform.storage.base import ExperimentRepository
from quantum_platform.storage.sqlite import SqliteExperimentRepository


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid.uuid4().hex


def create_app(
    settings: Settings | None = None,
    *,
    adapter: HardwareAdapter | None = None,
    queue: JobQueue | None = None,
    repo: ExperimentRepository | None = None,
    clock: Callable[[], datetime] = _utc_now,
    id_factory: Callable[[], str] = _new_id,
) -> FastAPI:
    settings = settings or Settings()
    repo = repo or SqliteExperimentRepository(settings.db_path)
    queue = queue or InMemoryJobQueue()
    adapter = adapter or SimulatorAdapter(
        latency_s=settings.simulator_latency_s, default_seed=settings.default_seed
    )
    service = ExecutionService(
        repo,
        queue,
        adapter,
        clock=clock,
        job_timeout_s=settings.job_timeout_s,
        concurrency=settings.worker_concurrency,
    )
    context = AppContext(
        settings=settings, repo=repo, service=service, clock=clock, id_factory=id_factory
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await service.start()
        try:
            yield
        finally:
            await service.stop()
            repo.close()

    app = FastAPI(title="Quantum Experiment Control API", version=API_VERSION, lifespan=lifespan)
    app.state.context = context
    install_error_handlers(app)
    install_request_context(app)
    app.include_router(router)
    app.include_router(ops_router)
    return app
