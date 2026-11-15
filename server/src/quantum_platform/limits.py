"""Validation limits enforced by the API."""

MAX_QUBITS = 10
MAX_SHOTS = 100_000
MAX_GATES = 1000
MAX_NAME_LENGTH = 100
MAX_SEED = 2**32 - 1
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20

SINGLE_QUBIT_GATES = frozenset({"H", "X", "Y", "Z", "S", "T"})
ROTATION_GATES = frozenset({"RX", "RY", "RZ"})
TWO_QUBIT_GATES = frozenset({"CNOT", "CZ"})
