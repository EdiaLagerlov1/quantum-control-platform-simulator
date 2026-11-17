"""Fixtures shared by every test directory. pytest finds this file automatically.

``info_dict`` and ``result_dict`` are sample API responses. The SDK unit tests feed them to the
SDK through a mock server, and the contract tests check that they match what the real server
sends. Keeping one copy means the mock data cannot quietly drift away from the real API.

``live_base_url`` is for tests that need a separately running server (smoke and integration).
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
import pytest

DEFAULT_BASE_URL = "http://localhost:8080"
READY_TIMEOUT_S = 10.0
POLL_INTERVAL_S = 0.2


@pytest.fixture
def info_dict() -> dict[str, Any]:
    """A well-formed experiment as the API returns it."""
    return {
        "id": "exp-1",
        "name": "bell",
        "status": "COMPLETED",
        "qubits": 2,
        "shots": 1000,
        "seed": 7,
        "gates": [
            {"name": "H", "target": 0, "control": None, "angle": None},
            {"name": "CNOT", "target": 1, "control": 0, "angle": None},
        ],
        "created_at": "2026-11-16T10:30:00+00:00",
        "updated_at": "2026-11-16T10:31:15+00:00",
        "error": None,
    }


@pytest.fixture
def result_dict() -> dict[str, Any]:
    """A well-formed experiment result as the API returns it."""
    return {
        "experiment_id": "exp-1",
        "counts": {"00": 480, "11": 520},
        "shots": 1000,
        "duration_ms": 12.5,
    }


def wait_until_ready(client: httpx.Client, timeout: float = READY_TIMEOUT_S) -> None:
    """Poll GET /ready until it returns 200, or fail with a message that says what to do."""
    deadline = time.monotonic() + timeout
    last_seen = "no response yet"
    while time.monotonic() < deadline:
        try:
            response = client.get("/ready")
        except httpx.TransportError as exc:
            last_seen = f"connection failed: {exc!r}"
        else:
            if response.status_code == 200:
                return
            last_seen = f"GET /ready returned {response.status_code}: {response.text[:200]}"
        time.sleep(POLL_INTERVAL_S)
    pytest.fail(
        f"The server at {client.base_url} was not ready after {timeout:.0f}s ({last_seen}). "
        "Start it with `docker compose up --build --wait`, or set API_BASE_URL."
    )


@pytest.fixture(scope="session")
def live_base_url() -> str:
    """The address of the running server, checked once per test run to be ready."""
    base_url = os.environ.get("API_BASE_URL", DEFAULT_BASE_URL)
    with httpx.Client(base_url=base_url, timeout=5.0) as client:
        wait_until_ready(client)
    return base_url
