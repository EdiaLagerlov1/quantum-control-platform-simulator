"""Exception hierarchy raised by the SDK."""

from __future__ import annotations

from typing import Any


class QuantumError(Exception):
    """Base class for every error raised by the SDK."""


class ValidationError(QuantumError, ValueError):
    """Input was rejected by the SDK before any request was sent."""


class TransportError(QuantumError):
    """The request could not be delivered or the connection broke."""


class RequestTimeoutError(TransportError):
    """Connecting to the API, or reading its response, timed out."""


class InvalidResponseError(QuantumError):
    """The API answered with a body the SDK could not interpret."""


class IncompatibleAPIVersionError(QuantumError):
    """The API reports a major version this SDK does not support."""


class WaitTimeoutError(QuantumError):
    """An experiment did not reach a terminal state within the wait timeout."""


class ExperimentFailedError(QuantumError):
    """An experiment finished in a terminal state other than COMPLETED."""

    def __init__(
        self,
        experiment_id: str,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        detail = f": {error_code}" if error_code else ""
        super().__init__(f"experiment {experiment_id} ended as {status}{detail}")
        self.experiment_id = experiment_id
        self.status = status
        self.error_code = error_code
        self.error_message = error_message


class APIError(QuantumError):
    """The API returned an error response."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        request_id: str | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(f"[{status_code} {code}] {message}")
        self.status_code = status_code
        self.code = code
        self.message = message
        self.request_id = request_id
        self.details = details


class InvalidRequestError(APIError):
    """400 or 422: the API rejected the request content."""


class AuthenticationError(APIError):
    """401: the API key is missing or not recognised."""


class PermissionDeniedError(APIError):
    """403: the API key may not access this resource."""


class NotFoundError(APIError):
    """404: the resource does not exist."""


class ConflictError(APIError):
    """409: the resource is not in a state that allows the operation."""


class RateLimitError(APIError):
    """429: too many requests."""


class ServerError(APIError):
    """5xx: the API failed to process the request."""


_STATUS_TO_ERROR: dict[int, type[APIError]] = {
    400: InvalidRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    422: InvalidRequestError,
    429: RateLimitError,
}


def error_class_for_status(status_code: int) -> type[APIError]:
    if status_code in _STATUS_TO_ERROR:
        return _STATUS_TO_ERROR[status_code]
    if status_code >= 500:
        return ServerError
    return APIError
