"""API tests for POST /v1/experiments. Requests go to the real application, nothing is faked."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

URL = "/v1/experiments"


@pytest.fixture
def valid_body() -> dict[str, Any]:
    """A well-formed request body."""
    return {"name": "bell", "qubits": 2, "shots": 100}


def test_valid_request_creates_experiment(
    api_client: TestClient, alice_headers: dict[str, str], valid_body: dict[str, Any]
) -> None:
    response = api_client.post(URL, json=valid_body, headers=alice_headers)

    assert response.status_code == 201
    created = response.json()
    assert isinstance(created["id"], str)
    assert created["id"] != ""
    assert created["name"] == "bell"
    assert created["qubits"] == 2
    assert created["shots"] == 100

    # Side effect: the experiment was really stored and can be fetched by its id.
    fetched = api_client.get(f"{URL}/{created['id']}", headers=alice_headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_missing_api_key_is_rejected_with_401(
    api_client: TestClient, valid_body: dict[str, Any]
) -> None:
    response = api_client.post(URL, json=valid_body)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_api_key"


def test_zero_qubits_is_rejected_with_422(
    api_client: TestClient, alice_headers: dict[str, str], valid_body: dict[str, Any]
) -> None:
    valid_body["qubits"] = 0

    response = api_client.post(URL, json=valid_body, headers=alice_headers)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    # The error points at the field that was wrong.
    assert any("qubits" in detail["loc"] for detail in error["details"])
