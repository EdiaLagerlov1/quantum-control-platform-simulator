"""Unit tests for the SDK experiment builder. No server and no mocks are involved."""

from __future__ import annotations

from typing import Any

import pytest

from quantum_sdk import Experiment, Gate, ValidationError
from quantum_sdk.models import MAX_GATES, MAX_NAME_LENGTH, MAX_QUBITS, MAX_SEED, MAX_SHOTS

# Values of the wrong type. True is included because Python treats bool as an int.
WRONG_TYPES = [1.5, "2", None, True]


@pytest.fixture
def experiment() -> Experiment:
    """A valid two-qubit experiment with no gates."""
    return Experiment(name="test", qubits=2)


class TestQubits:
    @pytest.mark.parametrize("qubits", [1, 5, MAX_QUBITS])
    def test_accepts_values_within_limits(self, qubits: int) -> None:
        assert Experiment(name="test", qubits=qubits).qubits == qubits

    @pytest.mark.parametrize("qubits", [-1, 0, MAX_QUBITS + 1])
    def test_rejects_values_outside_limits(self, qubits: int) -> None:
        with pytest.raises(ValidationError, match="qubits"):
            Experiment(name="test", qubits=qubits)

    @pytest.mark.parametrize("qubits", WRONG_TYPES)
    def test_rejects_non_integers(self, qubits: Any) -> None:
        with pytest.raises(ValidationError, match="qubits"):
            Experiment(name="test", qubits=qubits)


class TestShots:
    def test_defaults_to_1000(self) -> None:
        assert Experiment(name="test", qubits=1).shots == 1000

    @pytest.mark.parametrize("shots", [1, 1000, MAX_SHOTS])
    def test_accepts_values_within_limits(self, shots: int) -> None:
        assert Experiment(name="test", qubits=1, shots=shots).shots == shots

    @pytest.mark.parametrize("shots", [-1, 0, MAX_SHOTS + 1])
    def test_rejects_values_outside_limits(self, shots: int) -> None:
        with pytest.raises(ValidationError, match="shots"):
            Experiment(name="test", qubits=1, shots=shots)

    @pytest.mark.parametrize("shots", WRONG_TYPES)
    def test_rejects_non_integers(self, shots: Any) -> None:
        with pytest.raises(ValidationError, match="shots"):
            Experiment(name="test", qubits=1, shots=shots)


class TestNameAndSeed:
    @pytest.mark.parametrize("name", ["a", "a" * MAX_NAME_LENGTH])
    def test_accepts_names_within_limits(self, name: str) -> None:
        assert Experiment(name=name, qubits=1).name == name

    @pytest.mark.parametrize("name", ["", "a" * (MAX_NAME_LENGTH + 1), None, 42])
    def test_rejects_invalid_names(self, name: Any) -> None:
        with pytest.raises(ValidationError, match="name"):
            Experiment(name=name, qubits=1)

    @pytest.mark.parametrize("seed", [None, 0, MAX_SEED])
    def test_accepts_valid_seeds(self, seed: int | None) -> None:
        assert Experiment(name="test", qubits=1, seed=seed).seed == seed

    @pytest.mark.parametrize("seed", [-1, MAX_SEED + 1, 1.5, True])
    def test_rejects_invalid_seeds(self, seed: Any) -> None:
        with pytest.raises(ValidationError, match="seed"):
            Experiment(name="test", qubits=1, seed=seed)


class TestAddGateValid:
    def test_single_qubit_gate_is_stored(self, experiment: Experiment) -> None:
        experiment.add_gate("H", target=0)

        assert experiment.gates == [Gate(name="H", target=0)]

    def test_two_qubit_gate_is_stored(self, experiment: Experiment) -> None:
        experiment.add_gate("CNOT", control=0, target=1)

        assert experiment.gates == [Gate(name="CNOT", target=1, control=0)]

    def test_rotation_gate_stores_angle_as_float(self, experiment: Experiment) -> None:
        experiment.add_gate("RX", target=0, angle=1)

        angle = experiment.gates[0].angle
        assert angle == 1.0
        assert isinstance(angle, float)

    def test_highest_qubit_index_is_accepted(self, experiment: Experiment) -> None:
        experiment.add_gate("X", target=experiment.qubits - 1)

        assert experiment.gates[0].target == 1

    def test_gates_keep_insertion_order_and_calls_chain(self, experiment: Experiment) -> None:
        returned = experiment.add_gate("H", target=0).add_gate("CNOT", control=0, target=1)

        assert returned is experiment
        assert [gate.name for gate in experiment.gates] == ["H", "CNOT"]


class TestAddGateInvalid:
    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            pytest.param({"name": "FOO", "target": 0}, "unsupported gate", id="unknown-gate"),
            pytest.param({"name": "h", "target": 0}, "unsupported gate", id="lowercase-name"),
            pytest.param({"name": "H", "target": 2}, "target", id="target-equals-qubit-count"),
            pytest.param({"name": "H", "target": -1}, "target", id="negative-target"),
            pytest.param({"name": "H", "target": True}, "target", id="boolean-target"),
            pytest.param({"name": "CNOT", "target": 1}, "requires a control", id="missing-control"),
            pytest.param(
                {"name": "CNOT", "target": 1, "control": 1}, "different", id="control-is-target"
            ),
            pytest.param(
                {"name": "CNOT", "target": 1, "control": 2}, "control", id="control-out-of-range"
            ),
            pytest.param(
                {"name": "H", "target": 0, "control": 1},
                "does not take a control",
                id="control-on-single-qubit-gate",
            ),
            pytest.param({"name": "RX", "target": 0}, "angle", id="rotation-without-angle"),
            pytest.param(
                {"name": "RX", "target": 0, "angle": "pi"}, "angle", id="non-numeric-angle"
            ),
            pytest.param(
                {"name": "H", "target": 0, "angle": 0.5},
                "does not take an angle",
                id="angle-on-fixed-gate",
            ),
        ],
    )
    def test_rejects_invalid_gate(
        self, experiment: Experiment, kwargs: dict[str, Any], message: str
    ) -> None:
        with pytest.raises(ValidationError, match=message):
            experiment.add_gate(**kwargs)

    def test_rejected_gate_is_not_stored(self, experiment: Experiment) -> None:
        experiment.add_gate("H", target=0)

        with pytest.raises(ValidationError):
            experiment.add_gate("CNOT", target=1)

        assert experiment.gates == [Gate(name="H", target=0)]

    def test_gate_count_limit(self) -> None:
        experiment = Experiment(name="test", qubits=1)
        for _ in range(MAX_GATES):
            experiment.add_gate("X", target=0)

        with pytest.raises(ValidationError, match="at most"):
            experiment.add_gate("X", target=0)

        assert len(experiment.gates) == MAX_GATES


class TestPayload:
    def test_bell_state_payload(self) -> None:
        experiment = Experiment(name="bell_state", qubits=2, shots=500, seed=7)
        experiment.add_gate("H", target=0).add_gate("CNOT", control=0, target=1)

        assert experiment.to_payload() == {
            "name": "bell_state",
            "qubits": 2,
            "shots": 500,
            "seed": 7,
            "gates": [
                {"name": "H", "target": 0, "control": None, "angle": None},
                {"name": "CNOT", "target": 1, "control": 0, "angle": None},
            ],
        }

    def test_new_experiment_has_no_id_and_no_shared_gates(self) -> None:
        first = Experiment(name="first", qubits=1)
        second = Experiment(name="second", qubits=1)
        first.add_gate("X", target=0)

        assert first.id is None
        assert second.gates == []
