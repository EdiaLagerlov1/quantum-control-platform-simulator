"""Request and response schemas for API v1."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from quantum_platform import limits
from quantum_platform.storage.base import ExperimentRecord

GateName = Literal["H", "X", "Y", "Z", "S", "T", "RX", "RY", "RZ", "CNOT", "CZ"]


class GateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: GateName
    target: int = Field(ge=0)
    control: int | None = Field(default=None, ge=0)
    angle: float | None = Field(default=None, allow_inf_nan=False)

    @model_validator(mode="after")
    def check_shape(self) -> Self:
        if self.name in limits.TWO_QUBIT_GATES:
            if self.control is None:
                raise ValueError(f"gate {self.name} requires a control qubit")
            if self.control == self.target:
                raise ValueError("control and target must be different qubits")
        elif self.control is not None:
            raise ValueError(f"gate {self.name} does not take a control qubit")
        if self.name in limits.ROTATION_GATES:
            if self.angle is None:
                raise ValueError(f"gate {self.name} requires an angle")
        elif self.angle is not None:
            raise ValueError(f"gate {self.name} does not take an angle")
        return self


class ExperimentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=limits.MAX_NAME_LENGTH)
    qubits: int = Field(ge=1, le=limits.MAX_QUBITS)
    shots: int = Field(default=1000, ge=1, le=limits.MAX_SHOTS)
    seed: int | None = Field(default=None, ge=0, le=limits.MAX_SEED)
    gates: list[GateIn] = Field(default_factory=list, max_length=limits.MAX_GATES)

    @model_validator(mode="after")
    def check_qubit_indices(self) -> Self:
        for position, gate in enumerate(self.gates):
            for label, index in (("target", gate.target), ("control", gate.control)):
                if index is not None and index >= self.qubits:
                    raise ValueError(
                        f"gates[{position}].{label} is {index} but the experiment has "
                        f"{self.qubits} qubit(s)"
                    )
        return self


class GateOut(BaseModel):
    name: str
    target: int
    control: int | None = None
    angle: float | None = None


class ErrorInfo(BaseModel):
    code: str
    message: str


class ExperimentOut(BaseModel):
    id: str
    name: str
    status: str
    qubits: int
    shots: int
    seed: int | None
    gates: list[GateOut]
    created_at: datetime
    updated_at: datetime
    error: ErrorInfo | None = None

    @classmethod
    def from_record(cls, record: ExperimentRecord) -> ExperimentOut:
        error = None
        if record.error_code is not None:
            error = ErrorInfo(code=record.error_code, message=record.error_message or "")
        return cls(
            id=record.id,
            name=record.name,
            status=record.status.value,
            qubits=record.qubits,
            shots=record.shots,
            seed=record.seed,
            gates=[GateOut(**gate) for gate in record.gates],
            created_at=record.created_at,
            updated_at=record.updated_at,
            error=error,
        )


class ExperimentListOut(BaseModel):
    items: list[ExperimentOut]
    total: int
    limit: int
    offset: int


class ResultOut(BaseModel):
    experiment_id: str
    counts: dict[str, int]
    shots: int
    duration_ms: float
