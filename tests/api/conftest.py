"""Fixtures for the API tests. The real application runs inside the test process."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from support import FakeHardwareAdapter

from quantum_platform.app import create_app
from quantum_platform.settings import Settings


@pytest.fixture
def fake_hardware() -> FakeHardwareAdapter:
    """The hardware behind the application under test. Tests use it to set results or failures."""
    return FakeHardwareAdapter()


@pytest.fixture
def api_client(tmp_path: Path, fake_hardware: FakeHardwareAdapter) -> Iterator[TestClient]:
    """An HTTP client for a freshly started application with its own empty database.

    Everything is real except the hardware, which is replaced by ``fake_hardware``.
    The client sends no API key by default, so each test states who is calling.
    """
    app = create_app(Settings(db_path=str(tmp_path / "test.db")), adapter=fake_hardware)
    # Entering the ``with`` block starts the application (and its execution service);
    # leaving it shuts everything down.
    with TestClient(app) as client:
        yield client


@pytest.fixture
def alice_headers() -> dict[str, str]:
    """Headers that authenticate the request as alice (a development API key)."""
    return {"X-API-Key": "test-key"}
