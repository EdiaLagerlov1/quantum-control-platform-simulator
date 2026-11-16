"""Fixtures shared by the SDK unit tests. pytest finds this file automatically."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def info_dict() -> dict[str, Any]:
    """A well-formed experiment as the API returns it."""
    return {
        "id": "exp-1",
        "name": "bell",
        "status": "COMPLETED",
        "qubits": 2,
        "shots": 1000,
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
