"""Hardware abstraction. The execution service talks to hardware only through this module."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class GateSpec:
    name: str
    target: int
    control: int | None = None
    angle: float | None = None


@dataclass(frozen=True)
class ExperimentSpec:
    job_id: str
    qubits: int
    shots: int
    gates: tuple[GateSpec, ...]
    seed: int | None = None


@dataclass(frozen=True)
class ExecutionResult:
    """Measurement outcome.

    ``counts`` maps a bitstring to how often it was measured. Qubit 0 is the leftmost
    character. The counts must sum to the number of shots requested.
    """

    job_id: str
    counts: dict[str, int]
    shots: int
    duration_ms: float


class HardwareJobStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class HardwareError(Exception):
    """Base class for failures reported by a hardware adapter."""

    code = "hardware_error"


class HardwareUnavailable(HardwareError):
    code = "hardware_unavailable"


class HardwareBusy(HardwareError):
    code = "hardware_busy"


class HardwareTimeout(HardwareError):
    code = "hardware_timeout"


class InvalidConfiguration(HardwareError):
    code = "invalid_configuration"


class ConnectionLost(HardwareError):
    code = "connection_lost"


class HardwareAdapter(ABC):
    """Contract every hardware backend (real, simulated or fake) must honour."""

    @abstractmethod
    async def execute(self, experiment: ExperimentSpec) -> ExecutionResult:
        """Run the experiment to completion and return its measurement counts.

        Raises a :class:`HardwareError` subclass on failure. If the calling task is
        cancelled, the adapter stops work and lets ``asyncio.CancelledError`` propagate.
        """

    @abstractmethod
    async def cancel(self, job_id: str) -> None:
        """Stop the job if it is running. Unknown or finished jobs are ignored."""

    @abstractmethod
    async def get_status(self, job_id: str) -> HardwareJobStatus:
        """Report the adapter's view of the job. Jobs never seen are ``UNKNOWN``."""
