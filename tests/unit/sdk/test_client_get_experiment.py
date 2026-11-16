"""Unit tests for QuantumClient.get_experiment.

The client code is real. Only the server is replaced: respx intercepts each HTTP request
before it leaves the process and answers with the response the test prepared.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx

from quantum_sdk import (
    AuthenticationError,
    ExperimentInfo,
    InvalidResponseError,
    NotFoundError,
    QuantumClient,
    RetryPolicy,
)

BASE_URL = "https://api.test"
API_KEY = "test-key"
EXPERIMENT_URL = f"{BASE_URL}/v1/experiments/exp-1"


@pytest.fixture
def client() -> Iterator[QuantumClient]:
    """A client that makes a single attempt, so a test never waits for retries."""
    client = QuantumClient(BASE_URL, API_KEY, retry=RetryPolicy(max_attempts=1))
    yield client
    client.close()


def test_returns_experiment_and_sends_expected_request(
    client: QuantumClient, respx_mock: respx.MockRouter, info_dict: dict[str, Any]
) -> None:
    route = respx_mock.get(EXPERIMENT_URL).mock(return_value=httpx.Response(200, json=info_dict))

    info = client.get_experiment("exp-1")

    assert isinstance(info, ExperimentInfo)
    assert info.id == "exp-1"
    assert info.name == "bell"
    assert info.status == "COMPLETED"
    assert info.qubits == 2
    assert info.shots == 1000
    assert info.created_at == datetime(2026, 11, 16, 10, 30, 0, tzinfo=UTC)

    assert route.call_count == 1
    request = route.calls.last.request
    assert request.method == "GET"
    assert str(request.url) == EXPERIMENT_URL
    assert request.headers["X-API-Key"] == API_KEY


def test_401_raises_authentication_error(
    client: QuantumClient, respx_mock: respx.MockRouter
) -> None:
    body = {"error": {"code": "invalid_api_key", "message": "The API key is not recognised."}}
    respx_mock.get(EXPERIMENT_URL).mock(return_value=httpx.Response(401, json=body))

    with pytest.raises(AuthenticationError) as caught:
        client.get_experiment("exp-1")

    assert caught.value.status_code == 401
    assert caught.value.code == "invalid_api_key"
    assert caught.value.message == "The API key is not recognised."


def test_404_raises_not_found_error(client: QuantumClient, respx_mock: respx.MockRouter) -> None:
    body = {"error": {"code": "experiment_not_found", "message": "no such experiment"}}
    respx_mock.get(EXPERIMENT_URL).mock(return_value=httpx.Response(404, json=body))

    with pytest.raises(NotFoundError) as caught:
        client.get_experiment("exp-1")

    assert caught.value.status_code == 404
    assert caught.value.code == "experiment_not_found"
    assert caught.value.message == "no such experiment"


def test_non_json_body_raises_invalid_response_error(
    client: QuantumClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(EXPERIMENT_URL).mock(
        return_value=httpx.Response(200, text="<html>Bad gateway</html>")
    )

    with pytest.raises(InvalidResponseError, match="non-JSON"):
        client.get_experiment("exp-1")


def test_json_without_id_raises_invalid_response_error(
    client: QuantumClient, respx_mock: respx.MockRouter, info_dict: dict[str, Any]
) -> None:
    del info_dict["id"]
    respx_mock.get(EXPERIMENT_URL).mock(return_value=httpx.Response(200, json=info_dict))

    with pytest.raises(InvalidResponseError, match="malformed experiment"):
        client.get_experiment("exp-1")
