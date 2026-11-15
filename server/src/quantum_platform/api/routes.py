"""API v1 routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from quantum_platform import limits
from quantum_platform.api.deps import AppContext, Context, Owner
from quantum_platform.api.errors import ApiError
from quantum_platform.api.schemas import (
    ExperimentCreate,
    ExperimentListOut,
    ExperimentOut,
    ResultOut,
)
from quantum_platform.execution.states import JobStatus
from quantum_platform.storage.base import ExperimentRecord

router = APIRouter(prefix="/v1", tags=["experiments"])
ops_router = APIRouter(tags=["operations"])


def _load(context: AppContext, owner: str, experiment_id: str) -> ExperimentRecord:
    record = context.repo.get(experiment_id)
    if record is None:
        raise ApiError(404, "not_found", f"Experiment {experiment_id} does not exist.")
    if record.owner != owner:
        raise ApiError(403, "forbidden", "This experiment belongs to another owner.")
    return record


@router.post("/experiments", status_code=201)
async def create_experiment(
    body: ExperimentCreate, context: Context, owner: Owner
) -> ExperimentOut:
    now = context.clock()
    record = ExperimentRecord(
        id=context.id_factory(),
        owner=owner,
        name=body.name,
        qubits=body.qubits,
        shots=body.shots,
        gates=[gate.model_dump() for gate in body.gates],
        seed=body.seed,
        status=JobStatus.CREATED,
        created_at=now,
        updated_at=now,
    )
    context.repo.create(record)
    return ExperimentOut.from_record(record)


@router.get("/experiments")
async def list_experiments(
    context: Context,
    owner: Owner,
    limit: Annotated[int, Query(ge=1, le=limits.MAX_PAGE_SIZE)] = limits.DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExperimentListOut:
    records, total = context.repo.list_for_owner(owner, limit, offset)
    return ExperimentListOut(
        items=[ExperimentOut.from_record(record) for record in records],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str, context: Context, owner: Owner) -> ExperimentOut:
    return ExperimentOut.from_record(_load(context, owner, experiment_id))


@router.post("/experiments/{experiment_id}/submit", status_code=202)
async def submit_experiment(
    experiment_id: str, request: Request, context: Context, owner: Owner
) -> ExperimentOut:
    record = _load(context, owner, experiment_id)
    correlation_id: str | None = getattr(request.state, "correlation_id", None)
    if not await context.service.submit(experiment_id, correlation_id):
        current = _load(context, owner, experiment_id)
        raise ApiError(
            409,
            "invalid_state",
            f"Only a CREATED experiment can be submitted; this one is {current.status}.",
            {"status": current.status.value},
        )
    return ExperimentOut.from_record(_load(context, owner, record.id))


@router.post("/experiments/{experiment_id}/cancel")
async def cancel_experiment(experiment_id: str, context: Context, owner: Owner) -> ExperimentOut:
    _load(context, owner, experiment_id)
    if not await context.service.cancel(experiment_id):
        current = _load(context, owner, experiment_id)
        raise ApiError(
            409,
            "invalid_state",
            f"Only a QUEUED or RUNNING experiment can be cancelled; this one is {current.status}.",
            {"status": current.status.value},
        )
    return ExperimentOut.from_record(_load(context, owner, experiment_id))


@router.get("/experiments/{experiment_id}/result")
async def get_result(experiment_id: str, context: Context, owner: Owner) -> ResultOut:
    record = _load(context, owner, experiment_id)
    if (
        record.status is not JobStatus.COMPLETED
        or record.counts is None
        or record.duration_ms is None
    ):
        raise ApiError(
            409,
            "result_not_ready",
            f"Results exist only for COMPLETED experiments; this one is {record.status}.",
            {"status": record.status.value},
        )
    return ResultOut(
        experiment_id=record.id,
        counts=record.counts,
        shots=record.shots,
        duration_ms=record.duration_ms,
    )


@ops_router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is up and serving requests."""
    return {"status": "ok"}


@ops_router.get("/ready")
async def ready(context: Context) -> JSONResponse:
    """Readiness: the store is reachable and the workers are running."""
    checks = {"storage": context.repo.ping(), "workers": context.service.is_running}
    is_ready = all(checks.values())
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={
            "status": "ready" if is_ready else "not_ready",
            "checks": checks,
            "queue_depth": context.service.queue_depth,
        },
    )
