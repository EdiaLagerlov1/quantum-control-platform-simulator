"""Integration tests: the real SDK against the real server, with nothing faked in between.

The server runs in its container with the real simulator, exactly as it would be deployed.
Every call goes over HTTP through the public SDK, the way a physicist's script would make it.
They need a running server, so they are not part of the default run. Run them with:

    docker compose up --build --wait
    uv run pytest -m integration -v
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest

from quantum_sdk import AuthenticationError, Experiment, NotFoundError, QuantumClient

pytestmark = pytest.mark.integration

ALICE_KEY = "test-key"
SHOTS = 200


@pytest.fixture(scope="module")
def sdk(live_base_url: str) -> Iterator[QuantumClient]:
    """The public SDK client, pointed at the running server."""
    # The SDK adds the /v1 prefix itself, so it gets the bare server address.
    with QuantumClient(live_base_url, ALICE_KEY) as client:
        yield client


def bell_experiment(seed: int) -> Experiment:
    """A Bell state: H on qubit 0, then CNOT 0 -> 1. Only 00 and 11 can be measured."""
    name = f"bell-{uuid.uuid4().hex[:8]}"  # unique: the server is shared between tests
    return (
        Experiment(name=name, qubits=2, shots=SHOTS, seed=seed)
        .add_gate("H", 0)
        .add_gate("CNOT", 1, control=0)
    )


def test_bell_state_runs_end_to_end(sdk: QuantumClient) -> None:
    experiment = bell_experiment(seed=7)

    result = sdk.run(experiment, timeout=30)

    # Software contract: the result belongs to this experiment and accounts for every shot.
    assert experiment.id is not None
    assert result.experiment_id == experiment.id
    assert result.shots == SHOTS
    assert sum(result.counts.values()) == SHOTS
    # Physics: an entangled pair is always measured equal, never 01 or 10.
    assert set(result.counts) <= {"00", "11"}, f"impossible outcomes in {result.counts}"


def test_same_seed_gives_same_counts(sdk: QuantumClient) -> None:
    first = sdk.run(bell_experiment(seed=42), timeout=30)
    second = sdk.run(bell_experiment(seed=42), timeout=30)

    # The seed travels SDK -> API -> queue -> simulator. If any hop drops it, this fails.
    assert first.counts == second.counts


def test_unknown_experiment_raises_not_found(sdk: QuantumClient) -> None:
    with pytest.raises(NotFoundError) as caught:
        sdk.get_experiment("does-not-exist")

    # A wrong URL also gives 404 "not_found", so the type alone would pass for the wrong reason.
    # The message proves the server looked for this experiment and did not find it.
    assert "does-not-exist" in caught.value.message
    assert caught.value.request_id is not None  # what a user pastes into a bug report


def test_wrong_api_key_raises_authentication_error(live_base_url: str) -> None:
    with (
        QuantumClient(live_base_url, "not-a-real-key") as client,
        pytest.raises(AuthenticationError),
    ):
        client.get_experiment("any-id")
