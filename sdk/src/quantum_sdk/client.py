"""Synchronous client."""

from __future__ import annotations

import time
from collections.abc import Callable
from types import TracebackType
from typing import Any, Self

import httpx

from quantum_sdk import _core
from quantum_sdk.errors import ExperimentFailedError, ValidationError, WaitTimeoutError
from quantum_sdk.models import Experiment, ExperimentInfo, ExperimentPage, ExperimentResult
from quantum_sdk.retry import RetryPolicy


class QuantumClient:
    """Blocking client for the experiment API.

    ``transport``, ``sleep`` and ``clock`` exist so the client can be exercised without a
    network or real waiting.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 10.0,
        retry: RetryPolicy | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._retry = retry or RetryPolicy()
        self._sleep = sleep
        self._clock = clock
        self._http = httpx.Client(
            base_url=_core.check_base_url(base_url),
            headers=_core.build_headers(api_key),
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def create_experiment(
        self, name: str, qubits: int, shots: int = 1000, seed: int | None = None
    ) -> Experiment:
        """Build an experiment locally. Nothing is sent until it is submitted or run."""
        return Experiment(name=name, qubits=qubits, shots=shots, seed=seed)

    def submit(self, experiment: Experiment) -> ExperimentInfo:
        """Register the experiment with the API if needed, then queue it for execution."""
        if experiment.id is None:
            created = self._request("POST", "/experiments", json=experiment.to_payload())
            experiment.id = ExperimentInfo.from_dict(created).id
        data = self._request("POST", f"/experiments/{experiment.id}/submit")
        return ExperimentInfo.from_dict(data)

    def get_experiment(self, experiment_id: str) -> ExperimentInfo:
        return ExperimentInfo.from_dict(self._request("GET", f"/experiments/{experiment_id}"))

    def get_result(self, experiment_id: str) -> ExperimentResult:
        data = self._request("GET", f"/experiments/{experiment_id}/result")
        return ExperimentResult.from_dict(data)

    def cancel(self, experiment_id: str) -> ExperimentInfo:
        data = self._request("POST", f"/experiments/{experiment_id}/cancel")
        return ExperimentInfo.from_dict(data)

    def list_experiments(self, limit: int = 20, offset: int = 0) -> ExperimentPage:
        data = self._request("GET", "/experiments", params={"limit": limit, "offset": offset})
        return ExperimentPage.from_dict(data)

    def wait(
        self, experiment_id: str, timeout: float = 60.0, poll_interval: float = 0.1
    ) -> ExperimentInfo:
        """Poll until the experiment reaches a terminal state."""
        if timeout <= 0 or poll_interval <= 0:
            raise ValidationError("timeout and poll_interval must be positive")
        deadline = self._clock() + timeout
        while True:
            info = self.get_experiment(experiment_id)
            if info.is_terminal:
                return info
            if self._clock() >= deadline:
                raise WaitTimeoutError(
                    f"experiment {experiment_id} still {info.status} after {timeout}s"
                )
            self._sleep(poll_interval)

    def run(
        self, experiment: Experiment, timeout: float = 60.0, poll_interval: float = 0.1
    ) -> ExperimentResult:
        """Submit the experiment, wait for it to finish and return its result."""
        submitted = self.submit(experiment)
        info = self.wait(submitted.id, timeout=timeout, poll_interval=poll_interval)
        if info.status != "COMPLETED":
            raise ExperimentFailedError(info.id, info.status, info.error_code, info.error_message)
        return self.get_result(info.id)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        attempt = 1
        while True:
            try:
                response = self._http.request(
                    method, _core.API_PREFIX + path, json=json, params=params
                )
            except httpx.TransportError as exc:
                delay = self._retry.delay_for_exception(method, exc, attempt)
                if delay is None:
                    raise _core.wrap_transport_error(exc) from exc
            else:
                delay = self._retry.delay_for_response(method, response, attempt)
                if delay is None:
                    return _core.parse_response(response)
            self._sleep(delay)
            attempt += 1
