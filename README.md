# Quantum Control Platform (QA automation practice)

A locally runnable simulation of a quantum experiment control platform, built as a practice target for
QA automation work: a Python SDK, a REST API, an asynchronous execution service, and a hardware
abstraction with a deterministic simulator.

This is an independent educational project. It does not replicate any vendor's products or protocols.

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run uvicorn quantum_platform.main:app --port 8000
```

In a second terminal:

```bash
uv run python scripts/demo_bell.py
```

Expected output (the seed is fixed, so the counts are identical on every run):

```
counts:     {'00': 480, '11': 520}
```

Interactive API docs are at http://localhost:8000/docs.

### Run in a container

Requires Docker. This runs the server from the built image, configured only through environment
variables, the way a deployment would.

```bash
docker compose up --build --wait   # build, start, and wait until GET /ready returns 200
curl http://localhost:8080/ready
docker compose down                # stop and discard all data
```

The container listens on host port 8080 (override with `QP_PORT`), so it does not collide with a
local `uvicorn` on 8000. The database lives inside the container: every `down` followed by `up`
starts from an empty state. The variables in the table below can be set in the shell before
`docker compose up`.

### Configuration

| Variable | Default | Meaning |
|---|---|---|
| `QP_API_KEYS` | `test-key:alice,other-key:bob` | `key:owner` pairs |
| `QP_DB_PATH` | `quantum.db` | SQLite file |
| `QP_JOB_TIMEOUT_S` | `30` | Execution timeout per job |
| `QP_WORKER_CONCURRENCY` | `2` | Number of worker tasks |
| `QP_SIM_LATENCY_S` | `0.05` | Artificial simulator execution time; raise it to observe `RUNNING` |
| `QP_DEFAULT_SEED` | unset | Seed for experiments that do not carry one |

### Checks

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

## What is where

| Path | Owner | Contents |
|---|---|---|
| `sdk/src/quantum_sdk/` | provided | Sync and async clients, experiment builder, errors, retry policy |
| `server/src/quantum_platform/` | provided | API, execution service, hardware abstraction, simulator, storage |
| `scripts/demo_bell.py` | provided | Manual smoke check |
| `Dockerfile`, `compose.yaml` | provided | Container image and local deployment of the API server |
| `docs/superpowers/specs/` | provided | Design spec, including the API contract and state machine |
| `tests/` | **you** | The automation framework, fixtures, fakes and tests |
| `docs/qa/` | **you** | QA strategy, risk matrix, test plans |

The product code ships without automated tests on purpose. Writing them is the exercise.

## Acceptance criteria for the baseline

1. `uv sync`, then one command starts the server.
2. `scripts/demo_bell.py` prints counts containing only `00` and `11`, roughly 50/50, identical across runs.
3. A request without a valid API key returns a structured 401 with a request ID.
4. A queued or running experiment can be cancelled and ends in `CANCELLED`.
5. Ruff and mypy pass on both packages.

## Seams for test doubles

- SDK: `QuantumClient(..., transport=, sleep=, clock=, retry=)` and the same on `AsyncQuantumClient`.
- Server: `create_app(settings, adapter=, queue=, repo=, clock=, id_factory=)`.
- Hardware: implement `quantum_platform.hardware.HardwareAdapter`.
