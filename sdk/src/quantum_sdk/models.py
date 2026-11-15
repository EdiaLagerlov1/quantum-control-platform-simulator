"""Experiment builder and response models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from quantum_sdk.errors import InvalidResponseError, ValidationError

MAX_QUBITS = 10
MAX_SHOTS = 100_000
MAX_GATES = 1000
MAX_NAME_LENGTH = 100
MAX_SEED = 2**32 - 1

SINGLE_QUBIT_GATES = frozenset({"H", "X", "Y", "Z", "S", "T"})
ROTATION_GATES = frozenset({"RX", "RY", "RZ"})
TWO_QUBIT_GATES = frozenset({"CNOT", "CZ"})
SUPPORTED_GATES = SINGLE_QUBIT_GATES | ROTATION_GATES | TWO_QUBIT_GATES

TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"})


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True)
class Gate:
    name: str
    target: int
    control: int | None = None
    angle: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target": self.target,
            "control": self.control,
            "angle": self.angle,
        }


@dataclass
class Experiment:
    """A locally built experiment. It gets an ``id`` once registered with the API."""

    name: str
    qubits: int
    shots: int = 1000
    seed: int | None = None
    gates: list[Gate] = field(default_factory=list)
    id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not 1 <= len(self.name) <= MAX_NAME_LENGTH:
            raise ValidationError(f"name must be a string of 1 to {MAX_NAME_LENGTH} characters")
        if not _is_int(self.qubits) or not 1 <= self.qubits <= MAX_QUBITS:
            raise ValidationError(f"qubits must be an integer from 1 to {MAX_QUBITS}")
        if not _is_int(self.shots) or not 1 <= self.shots <= MAX_SHOTS:
            raise ValidationError(f"shots must be an integer from 1 to {MAX_SHOTS}")
        if self.seed is not None and (not _is_int(self.seed) or not 0 <= self.seed <= MAX_SEED):
            raise ValidationError(f"seed must be an integer from 0 to {MAX_SEED}")

    def add_gate(
        self,
        name: str,
        target: int,
        control: int | None = None,
        angle: float | None = None,
    ) -> Experiment:
        """Append a gate. Returns ``self`` so calls can be chained."""
        if name not in SUPPORTED_GATES:
            raise ValidationError(
                f"unsupported gate {name!r}; expected one of {sorted(SUPPORTED_GATES)}"
            )
        if len(self.gates) >= MAX_GATES:
            raise ValidationError(f"an experiment may contain at most {MAX_GATES} gates")
        self._check_qubit("target", target)
        if name in TWO_QUBIT_GATES:
            if control is None:
                raise ValidationError(f"gate {name} requires a control qubit")
            self._check_qubit("control", control)
            if control == target:
                raise ValidationError("control and target must be different qubits")
        elif control is not None:
            raise ValidationError(f"gate {name} does not take a control qubit")
        if name in ROTATION_GATES:
            if angle is None or isinstance(angle, bool) or not isinstance(angle, int | float):
                raise ValidationError(f"gate {name} requires a numeric angle in radians")
            angle = float(angle)
        elif angle is not None:
            raise ValidationError(f"gate {name} does not take an angle")
        self.gates.append(Gate(name=name, target=target, control=control, angle=angle))
        return self

    def _check_qubit(self, label: str, index: int) -> None:
        if not _is_int(index) or not 0 <= index < self.qubits:
            raise ValidationError(f"{label} must be an integer from 0 to {self.qubits - 1}")

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "qubits": self.qubits,
            "shots": self.shots,
            "seed": self.seed,
            "gates": [gate.to_dict() for gate in self.gates],
        }


@dataclass(frozen=True)
class ExperimentInfo:
    id: str
    name: str
    status: str
    qubits: int
    shots: int
    created_at: datetime
    updated_at: datetime
    error_code: str | None = None
    error_message: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @classmethod
    def from_dict(cls, data: Any) -> ExperimentInfo:
        try:
            error = data.get("error") or {}
            return cls(
                id=str(data["id"]),
                name=str(data["name"]),
                status=str(data["status"]),
                qubits=int(data["qubits"]),
                shots=int(data["shots"]),
                created_at=datetime.fromisoformat(data["created_at"]),
                updated_at=datetime.fromisoformat(data["updated_at"]),
                error_code=error.get("code"),
                error_message=error.get("message"),
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise InvalidResponseError(f"malformed experiment in API response: {exc!r}") from exc


@dataclass(frozen=True)
class ExperimentResult:
    experiment_id: str
    counts: dict[str, int]
    shots: int
    duration_ms: float

    @property
    def probabilities(self) -> dict[str, float]:
        return {bits: count / self.shots for bits, count in self.counts.items()}

    @classmethod
    def from_dict(cls, data: Any) -> ExperimentResult:
        try:
            return cls(
                experiment_id=str(data["experiment_id"]),
                counts={str(bits): int(count) for bits, count in data["counts"].items()},
                shots=int(data["shots"]),
                duration_ms=float(data["duration_ms"]),
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise InvalidResponseError(f"malformed result in API response: {exc!r}") from exc


@dataclass(frozen=True)
class ExperimentPage:
    items: list[ExperimentInfo]
    total: int
    limit: int
    offset: int

    @classmethod
    def from_dict(cls, data: Any) -> ExperimentPage:
        try:
            return cls(
                items=[ExperimentInfo.from_dict(item) for item in data["items"]],
                total=int(data["total"]),
                limit=int(data["limit"]),
                offset=int(data["offset"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidResponseError(f"malformed page in API response: {exc!r}") from exc
