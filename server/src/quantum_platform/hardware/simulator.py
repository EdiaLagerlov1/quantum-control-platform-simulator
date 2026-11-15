"""Deterministic statevector simulator behind the hardware abstraction."""

from __future__ import annotations

import asyncio
import cmath
import math
import random
import time
from collections import Counter

from quantum_platform.hardware.base import (
    ExecutionResult,
    ExperimentSpec,
    GateSpec,
    HardwareAdapter,
    HardwareJobStatus,
    InvalidConfiguration,
)
from quantum_platform.limits import MAX_QUBITS

type Matrix = tuple[complex, complex, complex, complex]

_SQRT_HALF = 1 / math.sqrt(2)
_FIXED_GATES: dict[str, Matrix] = {
    "H": (_SQRT_HALF, _SQRT_HALF, _SQRT_HALF, -_SQRT_HALF),
    "X": (0, 1, 1, 0),
    "Y": (0, -1j, 1j, 0),
    "Z": (1, 0, 0, -1),
    "S": (1, 0, 0, 1j),
    "T": (1, 0, 0, cmath.exp(1j * math.pi / 4)),
}


def _rotation(name: str, angle: float) -> Matrix:
    cos, sin = math.cos(angle / 2), math.sin(angle / 2)
    if name == "RX":
        return (cos, -1j * sin, -1j * sin, cos)
    if name == "RY":
        return (cos, -sin, sin, cos)
    return (cmath.exp(-1j * angle / 2), 0, 0, cmath.exp(1j * angle / 2))


def _apply_single(state: list[complex], qubit: int, matrix: Matrix) -> None:
    m00, m01, m10, m11 = matrix
    bit = 1 << qubit
    for index in range(len(state)):
        if index & bit:
            continue
        low, high = state[index], state[index | bit]
        state[index] = m00 * low + m01 * high
        state[index | bit] = m10 * low + m11 * high


def _apply_gate(state: list[complex], qubits: int, gate: GateSpec) -> None:
    if not 0 <= gate.target < qubits:
        raise InvalidConfiguration(f"gate {gate.name} targets qubit {gate.target}")
    if gate.name in _FIXED_GATES:
        _apply_single(state, gate.target, _FIXED_GATES[gate.name])
    elif gate.name in ("RX", "RY", "RZ"):
        if gate.angle is None:
            raise InvalidConfiguration(f"gate {gate.name} has no angle")
        _apply_single(state, gate.target, _rotation(gate.name, gate.angle))
    elif gate.name in ("CNOT", "CZ"):
        control = gate.control
        if control is None or not 0 <= control < qubits or control == gate.target:
            raise InvalidConfiguration(f"gate {gate.name} has an invalid control qubit")
        control_bit, target_bit = 1 << control, 1 << gate.target
        for index in range(len(state)):
            if not index & control_bit or index & target_bit:
                continue
            partner = index | target_bit
            if gate.name == "CNOT":
                state[index], state[partner] = state[partner], state[index]
            else:
                state[partner] = -state[partner]
    else:
        raise InvalidConfiguration(f"unsupported gate {gate.name!r}")


def simulate(spec: ExperimentSpec) -> dict[str, int]:
    """Return measurement counts for all qubits. Qubit 0 is the leftmost character."""
    if not 1 <= spec.qubits <= MAX_QUBITS:
        raise InvalidConfiguration(f"simulator supports 1 to {MAX_QUBITS} qubits")
    if spec.shots < 1:
        raise InvalidConfiguration("shots must be at least 1")
    state: list[complex] = [0j] * (1 << spec.qubits)
    state[0] = 1 + 0j
    for gate in spec.gates:
        _apply_gate(state, spec.qubits, gate)
    weights = [abs(amplitude) ** 2 for amplitude in state]
    rng = random.Random(spec.seed)
    samples = rng.choices(range(len(state)), weights=weights, k=spec.shots)
    counts = Counter(samples)
    return {
        "".join(str((index >> qubit) & 1) for qubit in range(spec.qubits)): count
        for index, count in sorted(counts.items())
    }


class SimulatorAdapter(HardwareAdapter):
    """Runs experiments on the in-process simulator.

    ``latency_s`` is an artificial execution time. ``default_seed`` applies to experiments
    that do not carry their own seed.
    """

    def __init__(self, latency_s: float = 0.0, default_seed: int | None = None) -> None:
        self._latency_s = latency_s
        self._default_seed = default_seed
        self._statuses: dict[str, HardwareJobStatus] = {}

    async def execute(self, experiment: ExperimentSpec) -> ExecutionResult:
        started = time.perf_counter()
        self._statuses[experiment.job_id] = HardwareJobStatus.RUNNING
        if experiment.seed is None and self._default_seed is not None:
            experiment = ExperimentSpec(
                job_id=experiment.job_id,
                qubits=experiment.qubits,
                shots=experiment.shots,
                gates=experiment.gates,
                seed=self._default_seed,
            )
        try:
            await asyncio.sleep(self._latency_s)
            counts = simulate(experiment)
        except asyncio.CancelledError:
            self._statuses[experiment.job_id] = HardwareJobStatus.CANCELLED
            raise
        except Exception:
            self._statuses[experiment.job_id] = HardwareJobStatus.FAILED
            raise
        self._statuses[experiment.job_id] = HardwareJobStatus.COMPLETED
        return ExecutionResult(
            job_id=experiment.job_id,
            counts=counts,
            shots=experiment.shots,
            duration_ms=(time.perf_counter() - started) * 1000,
        )

    async def cancel(self, job_id: str) -> None:
        if self._statuses.get(job_id) is HardwareJobStatus.RUNNING:
            self._statuses[job_id] = HardwareJobStatus.CANCELLED

    async def get_status(self, job_id: str) -> HardwareJobStatus:
        return self._statuses.get(job_id, HardwareJobStatus.UNKNOWN)
