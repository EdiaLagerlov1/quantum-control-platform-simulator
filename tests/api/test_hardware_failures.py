"""API tests for running an experiment, with the hardware replaced by a fake.

Each test decides what the hardware does, runs an experiment through the real API and
execution service, and checks what the user sees.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from support import FakeHardwareAdapter, wait_until_terminal

from quantum_platform.hardware import (
    ConnectionLost,
    HardwareBusy,
    HardwareError,
    HardwareTimeout,
    HardwareUnavailable,
    InvalidConfiguration,
)

URL = "/v1/experiments"


def run_experiment(client: TestClient, headers: dict[str, str], shots: int = 100) -> dict[str, Any]:
    """Create and submit an experiment, wait for it to finish, and return its final state."""
    created = client.post(URL, json={"name": "bell", "qubits": 2, "shots": shots}, headers=headers)
    assert created.status_code == 201, created.text
    experiment_id = created.json()["id"]

    submitted = client.post(f"{URL}/{experiment_id}/submit", headers=headers)
    assert submitted.status_code == 202, submitted.text

    return wait_until_terminal(client, experiment_id, headers)


def test_successful_run_returns_the_counts_from_the_hardware(
    api_client: TestClient, alice_headers: dict[str, str], fake_hardware: FakeHardwareAdapter
) -> None:
    fake_hardware.counts = {"00": 60, "11": 40}

    final = run_experiment(api_client, alice_headers, shots=100)

    assert final["status"] == "COMPLETED"
    assert final["error"] is None

    result = api_client.get(f"{URL}/{final['id']}/result", headers=alice_headers)
    assert result.status_code == 200, result.text
    assert result.json()["counts"] == {"00": 60, "11": 40}
    assert result.json()["shots"] == 100

    # The hardware was asked to run this experiment exactly once, with the requested shots.
    assert [spec.job_id for spec in fake_hardware.executed] == [final["id"]]
    assert fake_hardware.executed[0].shots == 100


def test_connection_lost_ends_as_failed_with_the_hardware_error(
    api_client: TestClient, alice_headers: dict[str, str], fake_hardware: FakeHardwareAdapter
) -> None:
    fake_hardware.fail_with = ConnectionLost("link to the controller dropped")

    final = run_experiment(api_client, alice_headers)

    assert final["status"] == "FAILED"
    assert final["error"] == {
        "code": "connection_lost",
        "message": "link to the controller dropped",
    }

    # A failed experiment has no result to return.
    result = api_client.get(f"{URL}/{final['id']}/result", headers=alice_headers)
    assert result.status_code == 409, result.text
    assert result.json()["error"]["code"] == "result_not_ready"


@pytest.mark.parametrize(
    ("hardware_error", "expected_code"),
    [
        pytest.param(HardwareUnavailable("offline"), "hardware_unavailable", id="unavailable"),
        pytest.param(HardwareBusy("in use"), "hardware_busy", id="busy"),
        pytest.param(HardwareTimeout("no answer"), "hardware_timeout", id="timeout"),
        pytest.param(InvalidConfiguration("bad setup"), "invalid_configuration", id="config"),
    ],
)
def test_each_hardware_error_is_reported_with_its_own_code(
    api_client: TestClient,
    alice_headers: dict[str, str],
    fake_hardware: FakeHardwareAdapter,
    hardware_error: HardwareError,
    expected_code: str,
) -> None:
    fake_hardware.fail_with = hardware_error

    final = run_experiment(api_client, alice_headers)

    assert final["status"] == "FAILED"
    assert final["error"]["code"] == expected_code


def test_counts_that_do_not_add_up_to_the_shots_are_rejected(
    api_client: TestClient, alice_headers: dict[str, str], fake_hardware: FakeHardwareAdapter
) -> None:
    fake_hardware.counts = {"00": 60, "11": 30}  # 90 measurements for 100 shots

    final = run_experiment(api_client, alice_headers, shots=100)

    assert final["status"] == "FAILED"
    assert final["error"]["code"] == "malformed_result"
