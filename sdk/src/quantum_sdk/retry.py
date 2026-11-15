"""Retry policy shared by the sync and async clients."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

# The request never reached the server, so repeating it cannot duplicate work.
_NEVER_SENT = (httpx.ConnectError, httpx.ConnectTimeout)


@dataclass(frozen=True)
class RetryPolicy:
    """Decides whether a failed attempt is retried and how long to wait first.

    ``max_attempts`` counts the first try, so ``max_attempts=1`` disables retries.
    """

    max_attempts: int = 3
    base_delay: float = 0.2
    multiplier: float = 2.0
    max_delay: float = 5.0
    # Retried for every method: the server states it did not process the request.
    always_retry_statuses: frozenset[int] = frozenset({429, 503})
    # Retried only for GET: the request may have been processed.
    idempotent_retry_statuses: frozenset[int] = frozenset({502, 504})

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay < 0 or self.max_delay < 0 or self.multiplier < 1:
            raise ValueError("delays must be non-negative and multiplier at least 1")

    def backoff(self, attempt: int) -> float:
        """Delay after the given 1-based attempt number."""
        return min(self.max_delay, self.base_delay * self.multiplier ** (attempt - 1))

    def delay_for_response(
        self, method: str, response: httpx.Response, attempt: int
    ) -> float | None:
        """Seconds to wait before retrying, or ``None`` to accept the response as final."""
        if attempt >= self.max_attempts:
            return None
        status = response.status_code
        retryable = status in self.always_retry_statuses or (
            method.upper() == "GET" and status in self.idempotent_retry_statuses
        )
        if not retryable:
            return None
        retry_after = _parse_retry_after(response.headers.get("retry-after"))
        if retry_after is not None:
            return min(self.max_delay, retry_after)
        return self.backoff(attempt)

    def delay_for_exception(
        self, method: str, exc: httpx.TransportError, attempt: int
    ) -> float | None:
        """Seconds to wait before retrying, or ``None`` to give up."""
        if attempt >= self.max_attempts:
            return None
        if isinstance(exc, _NEVER_SENT) or method.upper() == "GET":
            return self.backoff(attempt)
        return None


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return seconds if seconds >= 0 else None
