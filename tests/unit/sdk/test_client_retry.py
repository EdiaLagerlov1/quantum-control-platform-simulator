"""Unit tests for the retry behaviour of QuantumClient.get_experiment.

The server is replaced by respx, and the client's ``sleep`` is replaced by a function that
records each requested wait, so no test waits for real.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx

from quantum_sdk import ExperimentInfo, QuantumClient, ServerError

BASE_URL = "https://api.test"
API_KEY = "test-key"
EXPERIMENT_URL = f"{BASE_URL}/v1/experiments/exp-1"


@pytest.fixture
def waits() -> list[float]:
    """Every wait the client asks for is appended here instead of being slept."""
    return []


@pytest.fixture
def client(waits: list[float]) -> Iterator[QuantumClient]:
    """A client with the default retry policy whose sleep only records the delay."""
    client = QuantumClient(BASE_URL, API_KEY, sleep=waits.append)
    yield client
    client.close()


def test_503_then_200_is_retried_and_succeeds(
    client: QuantumClient,
    waits: list[float],
    respx_mock: respx.MockRouter,
    info_dict: dict[str, Any],
) -> None:
    route = respx_mock.get(EXPERIMENT_URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=info_dict)]
    )

    info = client.get_experiment("exp-1")

    assert isinstance(info, ExperimentInfo)
    assert info.id == "exp-1"
    assert route.call_count == 2
    # One wait between the two attempts: the policy's base delay.
    assert waits == [0.2]


def test_503_on_every_attempt_raises_server_error(
    client: QuantumClient, waits: list[float], respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(EXPERIMENT_URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(503), httpx.Response(503)]
    )

    with pytest.raises(ServerError) as caught:
        client.get_experiment("exp-1")

    assert caught.value.status_code == 503
    assert route.call_count == 3
    # Two waits between three attempts, the second twice as long. No wait after the last one.
    assert waits == [0.2, 0.4]
