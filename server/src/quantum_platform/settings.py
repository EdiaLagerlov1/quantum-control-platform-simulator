"""Runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Development defaults only. Override with QP_API_KEYS="key:owner,key:owner".
_DEFAULT_API_KEYS = "test-key:alice,other-key:bob"


def _parse_api_keys(raw: str) -> dict[str, str]:
    keys: dict[str, str] = {}
    for entry in raw.split(","):
        key, sep, owner = entry.strip().partition(":")
        if not sep or not key or not owner:
            raise ValueError(f"invalid API key entry {entry!r}; expected 'key:owner'")
        keys[key] = owner
    return keys


@dataclass(frozen=True)
class Settings:
    api_keys: dict[str, str] = field(default_factory=lambda: _parse_api_keys(_DEFAULT_API_KEYS))
    db_path: str = "quantum.db"
    job_timeout_s: float = 30.0
    worker_concurrency: int = 2
    # Artificial execution time of the simulator, so RUNNING is observable.
    simulator_latency_s: float = 0.05
    # Used when an experiment does not specify a seed. None means non-deterministic.
    default_seed: int | None = None

    @classmethod
    def from_env(cls) -> Settings:
        seed = os.environ.get("QP_DEFAULT_SEED")
        return cls(
            api_keys=_parse_api_keys(os.environ.get("QP_API_KEYS", _DEFAULT_API_KEYS)),
            db_path=os.environ.get("QP_DB_PATH", "quantum.db"),
            job_timeout_s=float(os.environ.get("QP_JOB_TIMEOUT_S", "30")),
            worker_concurrency=int(os.environ.get("QP_WORKER_CONCURRENCY", "2")),
            simulator_latency_s=float(os.environ.get("QP_SIM_LATENCY_S", "0.05")),
            default_seed=int(seed) if seed else None,
        )
