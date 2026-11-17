"""Fixtures for the smoke tests. The server is a separate, already running process."""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest


@pytest.fixture(scope="session")
def live_client(live_base_url: str) -> Iterator[httpx.Client]:
    """An HTTP client for the running server. Created once for the whole test run."""
    with httpx.Client(base_url=live_base_url, timeout=5.0) as client:
        yield client
