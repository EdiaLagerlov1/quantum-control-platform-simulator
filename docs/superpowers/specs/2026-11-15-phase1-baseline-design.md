# Phase 1 baseline design

Date: 2026-11-15
Scope: Phase 1 only (architecture plus a thin, working vertical slice). Later phases get their own specs.

This is an independent educational simulation. It does not replicate any vendor's products or protocols.

## Goal

A locally runnable slice of a quantum experiment control platform that a QA Automation Lead candidate can
test against: SDK, REST API, asynchronous execution, and a hardware abstraction with a deterministic simulator.
The product code is provided. The automation framework, tests, and fakes are written by the learner.

## Architecture

```
quantum_sdk ──HTTP──▶ FastAPI app ──▶ JobQueue ──▶ ExecutionService ──▶ HardwareAdapter ──▶ SimulatorAdapter
 (httpx)               │              (asyncio)          │
                       └────────▶ ExperimentRepository ◀─┘
                                     (SQLite)
```

The API and the workers run in one process. Workers are asyncio tasks started by the app lifespan.
The queue, repository, and hardware adapter are interfaces, so Redis, a separate worker process, and
PostgreSQL can replace the in-process versions in Phase 5 without changing callers.

## Repository layout

Two installable packages in one uv workspace. The SDK must not import server code; it knows the server
only through HTTP, which is what makes contract testing meaningful.

```
sdk/src/quantum_sdk/            client, async client, models, errors, retry policy
server/src/quantum_platform/
    api/                        routes, schemas, errors, dependencies, request-context middleware
    execution/                  states, queue, execution service (workers)
    hardware/                   HardwareAdapter interface, SimulatorAdapter
    storage/                    repository interface, SQLite implementation
    app.py                      create_app(settings, adapter=, queue=, repo=, clock=, id_factory=)
    main.py                     uvicorn entry point
scripts/demo_bell.py            manual smoke check, not a test
tests/                          empty; owned by the learner
```

## Components

**SDK.** Local experiment builder with client-side validation; sync and async clients; `X-API-Key` auth;
retry with exponential backoff; request timeouts; HTTP status to exception mapping; API major-version check
through the `X-API-Version` response header.

Retry policy: connection failures are always retried (the request never arrived). Other transport errors and
502/504 are retried only for GET. 429 and 503 are retried for every method and honour `Retry-After`.
Delay is `min(max_delay, base_delay * multiplier ** (attempt - 1))`.

**API.** Endpoints under `/v1`:

| Method | Path | Success | Notes |
|---|---|---|---|
| POST | `/v1/experiments` | 201 | Validates and stores an experiment in `CREATED` |
| GET | `/v1/experiments` | 200 | Caller's experiments, newest first, `limit` 1..100, `offset` >= 0 |
| GET | `/v1/experiments/{id}` | 200 | |
| POST | `/v1/experiments/{id}/submit` | 202 | 409 unless `CREATED` |
| POST | `/v1/experiments/{id}/cancel` | 200 | 409 unless `QUEUED` or `RUNNING` |
| GET | `/v1/experiments/{id}/result` | 200 | 409 `result_not_ready` unless `COMPLETED` |
| GET | `/health`, `/ready` | 200 | Unauthenticated; `/ready` is 503 when the store or workers are down |

Missing or unknown API key is 401. Another owner's experiment is 403. Unknown id is 404.
Every response carries `X-Request-ID`, `X-Correlation-ID`, and `X-API-Version`. Errors use one shape:
`{"error": {"code", "message", "request_id", "details"}}`.

Limits: 1..10 qubits, 1..100000 shots, at most 1000 gates, name 1..100 characters, seed 0..2^32-1.
Gates: `H X Y Z S T` (one qubit), `RX RY RZ` (one qubit, `angle` required), `CNOT CZ` (`control` required).

**Execution service.** States and allowed transitions:

```
CREATED → QUEUED → RUNNING → COMPLETED | FAILED | TIMED_OUT
              └────────┴───▶ CANCELLED
```

Every transition is a compare-and-set in the repository, so a late worker result cannot overwrite a
cancellation. A result whose counts do not sum to the requested shots fails the job as `malformed_result`.
On startup, `QUEUED` jobs are re-enqueued and `RUNNING` jobs are failed as `worker_interrupted`.

**Hardware layer.** `HardwareAdapter` defines `execute`, `cancel`, and `get_status`, with typed errors:
`HardwareUnavailable`, `HardwareBusy`, `HardwareTimeout`, `InvalidConfiguration`, `ConnectionLost`.
`SimulatorAdapter` is a pure-Python statevector simulator. Qubit 0 is the leftmost character of a bitstring.
With a seed, counts are reproducible.

**Observability.** JSON logs with request and correlation IDs. The correlation ID of the submit request is
stored on the job and attached to worker logs.

## Injection seams

- SDK: `transport`, `sleep`, `clock`, `retry` policy.
- Server: `create_app(settings, adapter, queue, repo, clock, id_factory)`.

## Deferred

Redis and a real task queue, PostgreSQL, Docker Compose, the dashboard, metrics, rate limiting, idempotency
keys, pulse sequences. Each is added before the phase that tests it.

## Acceptance criteria

1. `uv sync`, then one command starts the server.
2. `scripts/demo_bell.py` prints counts containing only `00` and `11`, roughly 50/50, identical across runs
   with the same seed.
3. A request without a valid API key returns a structured 401 with a request ID.
4. A queued or running experiment can be cancelled and ends in `CANCELLED`.
5. Ruff and mypy pass on both packages.

## Ownership

Provided: everything under `sdk/`, `server/`, `scripts/`. Verified with the demo script, Ruff, and mypy only.
Learner: everything under `tests/`, the QA strategy and risk documents, the fake hardware adapter, CI.
