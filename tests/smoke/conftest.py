"""Fixtures for the smoke tests. The server is a separate, already running process."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator

import httpx
import pytest

DEFAULT_BASE_URL = "http://localhost:8080"
READY_TIMEOUT_S = 10.0
POLL_INTERVAL_S = 0.2


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
def live_client() -> Iterator[httpx.Client]:
    """An HTTP client for the running server. Created once for the whole test run."""
    base_url = os.environ.get("API_BASE_URL", DEFAULT_BASE_URL)
    with httpx.Client(base_url=base_url, timeout=5.0) as client:
        wait_until_ready(client)
        yield client
