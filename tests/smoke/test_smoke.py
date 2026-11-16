"""Smoke tests: is the deployed server alive, and does the main path work?

They need a running server, so they are not part of the default run. Run them with:

    docker compose up --build --wait
    uv run pytest -m smoke -v
"""

from __future__ import annotations

import uuid

import httpx
import pytest

pytestmark = pytest.mark.smoke

ALICE = {"X-API-Key": "test-key"}


def test_created_experiment_can_be_fetched(live_client: httpx.Client) -> None:
    # A unique name: the server is shared, so the test only looks at what it created itself.
    name = f"smoke-{uuid.uuid4().hex[:8]}"

    created = live_client.post(
        "/v1/experiments", json={"name": name, "qubits": 2, "shots": 100}, headers=ALICE
    )
    assert created.status_code == 201, created.text
    experiment_id = created.json()["id"]

    fetched = live_client.get(f"/v1/experiments/{experiment_id}", headers=ALICE)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["id"] == experiment_id
    assert fetched.json()["name"] == name
