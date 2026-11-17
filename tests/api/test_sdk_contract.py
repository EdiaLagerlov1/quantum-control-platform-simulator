"""Contract tests between the SDK and the server.

The SDK unit tests talk to a mock server whose answers we wrote by hand, and the API tests talk to
the real server without the SDK. Both can pass while the two sides disagree. These tests close
that gap from both directions, without a network and in milliseconds:

A. Our mock data looks like what the real server sends (checked against the server's schema).
B. What the real server sends can be read by the SDK (real responses fed to the SDK's parsers).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from support import FakeHardwareAdapter, wait_until_terminal

from quantum_platform.api.schemas import ExperimentListOut, ExperimentOut, ResultOut
from quantum_sdk import ExperimentInfo, ExperimentPage, ExperimentResult, NotFoundError
from quantum_sdk._core import parse_response  # the exact code path the SDK runs on every reply

URL = "/v1/experiments"


# --- A. The mock data used by the SDK unit tests matches the server's response schema ---------


def test_mock_experiment_matches_server_schema(info_dict: dict[str, Any]) -> None:
    # model_validate raises if a field the server always sends is missing or has the wrong type.
    ExperimentOut.model_validate(info_dict)


def test_mock_result_matches_server_schema(result_dict: dict[str, Any]) -> None:
    ResultOut.model_validate(result_dict)


# --- B. Real server responses can be read by the SDK ------------------------------------------


@pytest.fixture
def created(api_client: TestClient, alice_headers: dict[str, str]) -> dict[str, Any]:
    """A real POST /v1/experiments response body."""
    response = api_client.post(
        URL, json={"name": "bell", "qubits": 2, "shots": 100, "seed": 7}, headers=alice_headers
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def test_sdk_reads_a_real_experiment(created: dict[str, Any]) -> None:
    info = ExperimentInfo.from_dict(created)

    assert info.id == created["id"]
    assert info.name == "bell"
    assert info.status == "CREATED"
    assert info.qubits == 2
    assert info.shots == 100


def test_sdk_reads_a_real_result(
    api_client: TestClient,
    alice_headers: dict[str, str],
    fake_hardware: FakeHardwareAdapter,
    created: dict[str, Any],
) -> None:
    fake_hardware.counts = {"00": 60, "11": 40}
    experiment_id = created["id"]
    api_client.post(f"{URL}/{experiment_id}/submit", headers=alice_headers)
    wait_until_terminal(api_client, experiment_id, alice_headers)

    response = api_client.get(f"{URL}/{experiment_id}/result", headers=alice_headers)
    result = ExperimentResult.from_dict(parse_response(response))

    assert result.experiment_id == experiment_id
    assert result.counts == {"00": 60, "11": 40}
    assert result.shots == 100


def test_sdk_reads_a_real_page(
    api_client: TestClient, alice_headers: dict[str, str], created: dict[str, Any]
) -> None:
    response = api_client.get(URL, headers=alice_headers)
    ExperimentListOut.model_validate(response.json())  # sanity: the server obeys its own schema

    page = ExperimentPage.from_dict(parse_response(response))

    assert [item.id for item in page.items] == [created["id"]]
    assert page.total == 1


def test_sdk_accepts_the_server_api_version(
    api_client: TestClient, alice_headers: dict[str, str], created: dict[str, Any]
) -> None:
    # The server stamps every reply with X-API-Version, and the SDK refuses a major version it
    # does not support. A version bump on one side only must fail here, not at a customer.
    response = api_client.get(f"{URL}/{created['id']}", headers=alice_headers)

    assert "x-api-version" in response.headers
    parse_response(response)  # raises IncompatibleAPIVersionError on a mismatch


def test_sdk_reads_a_real_error(api_client: TestClient, alice_headers: dict[str, str]) -> None:
    response = api_client.get(f"{URL}/does-not-exist", headers=alice_headers)

    with pytest.raises(NotFoundError) as caught:
        parse_response(response)

    # The SDK must find the code and request id inside the server's error envelope.
    assert caught.value.code == response.json()["error"]["code"]
    assert caught.value.request_id == response.json()["error"]["request_id"]
    assert caught.value.request_id is not None
