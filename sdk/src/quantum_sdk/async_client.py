"""Asynchronous client. Mirrors :class:`quantum_sdk.client.QuantumClient`."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Any, Self

import httpx

from quantum_sdk import _core
from quantum_sdk.errors import ExperimentFailedError, ValidationError, WaitTimeoutError
from quantum_sdk.models import Experiment, ExperimentInfo, ExperimentPage, ExperimentResult
from quantum_sdk.retry import RetryPolicy


class AsyncQuantumClient:
    """Non-blocking client for the experiment API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 10.0,
        retry: RetryPolicy | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._retry = retry or RetryPolicy()
        self._sleep = sleep
        self._clock = clock
        self._http = httpx.AsyncClient(
            base_url=_core.check_base_url(base_url),
            headers=_core.build_headers(api_key),
            timeout=timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    def create_experiment(
        self, name: str, qubits: int, shots: int = 1000, seed: int | None = None
    ) -> Experiment:
        """Build an experiment locally. Nothing is sent until it is submitted or run."""
        return Experiment(name=name, qubits=qubits, shots=shots, seed=seed)

    async def submit(self, experiment: Experiment) -> ExperimentInfo:
        """Register the experiment with the API if needed, then queue it for execution."""
        if experiment.id is None:
            created = await self._request("POST", "/experiments", json=experiment.to_payload())
            experiment.id = ExperimentInfo.from_dict(created).id
        data = await self._request("POST", f"/experiments/{experiment.id}/submit")
        return ExperimentInfo.from_dict(data)

    async def get_experiment(self, experiment_id: str) -> ExperimentInfo:
        return ExperimentInfo.from_dict(await self._request("GET", f"/experiments/{experiment_id}"))

    async def get_result(self, experiment_id: str) -> ExperimentResult:
        data = await self._request("GET", f"/experiments/{experiment_id}/result")
        return ExperimentResult.from_dict(data)

    async def cancel(self, experiment_id: str) -> ExperimentInfo:
        data = await self._request("POST", f"/experiments/{experiment_id}/cancel")
        return ExperimentInfo.from_dict(data)

    async def list_experiments(self, limit: int = 20, offset: int = 0) -> ExperimentPage:
        data = await self._request("GET", "/experiments", params={"limit": limit, "offset": offset})
        return ExperimentPage.from_dict(data)

    async def wait(
        self, experiment_id: str, timeout: float = 60.0, poll_interval: float = 0.1
    ) -> ExperimentInfo:
        """Poll until the experiment reaches a terminal state."""
        if timeout <= 0 or poll_interval <= 0:
            raise ValidationError("timeout and poll_interval must be positive")
        deadline = self._clock() + timeout
        while True:
            info = await self.get_experiment(experiment_id)
            if info.is_terminal:
                return info
            if self._clock() >= deadline:
                raise WaitTimeoutError(
                    f"experiment {experiment_id} still {info.status} after {timeout}s"
                )
            await self._sleep(poll_interval)

    async def run(
        self, experiment: Experiment, timeout: float = 60.0, poll_interval: float = 0.1
    ) -> ExperimentResult:
        """Submit the experiment, wait for it to finish and return its result."""
        submitted = await self.submit(experiment)
        info = await self.wait(submitted.id, timeout=timeout, poll_interval=poll_interval)
        if info.status != "COMPLETED":
            raise ExperimentFailedError(info.id, info.status, info.error_code, info.error_message)
        return await self.get_result(info.id)

    async def _request(
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
                response = await self._http.request(
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
            await self._sleep(delay)
            attempt += 1
