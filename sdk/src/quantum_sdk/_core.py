"""Protocol details shared by the sync and async clients."""

from __future__ import annotations

from typing import Any

import httpx

from quantum_sdk.errors import (
    IncompatibleAPIVersionError,
    InvalidResponseError,
    RequestTimeoutError,
    TransportError,
    ValidationError,
    error_class_for_status,
)

API_PREFIX = "/v1"
SUPPORTED_API_MAJOR = 1
SDK_VERSION = "0.1.0"


def build_headers(api_key: str) -> dict[str, str]:
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValidationError("api_key must be a non-empty string")
    return {
        "X-API-Key": api_key,
        "Accept": "application/json",
        "User-Agent": f"quantum-sdk/{SDK_VERSION}",
    }


def check_base_url(base_url: str) -> str:
    if not isinstance(base_url, str) or not base_url.startswith(("http://", "https://")):
        raise ValidationError("base_url must start with http:// or https://")
    return base_url.rstrip("/")


def parse_response(response: httpx.Response) -> Any:
    """Return the decoded JSON body, or raise the SDK error matching the response."""
    _check_api_version(response)
    if response.status_code >= 400:
        raise _api_error(response)
    try:
        return response.json()
    except ValueError as exc:
        raise InvalidResponseError(
            f"API returned a non-JSON body with status {response.status_code}"
        ) from exc


def wrap_transport_error(exc: httpx.TransportError) -> TransportError:
    if isinstance(exc, httpx.TimeoutException):
        return RequestTimeoutError(f"request timed out: {exc!r}")
    return TransportError(f"request failed: {exc!r}")


def _check_api_version(response: httpx.Response) -> None:
    version = response.headers.get("x-api-version")
    if version is None:
        return
    major = version.split(".", 1)[0]
    if major != str(SUPPORTED_API_MAJOR):
        raise IncompatibleAPIVersionError(
            f"API version {version} is not supported; this SDK supports {SUPPORTED_API_MAJOR}.x"
        )


def _api_error(response: httpx.Response) -> Exception:
    code = "unknown_error"
    message = response.text[:500] or response.reason_phrase
    request_id = response.headers.get("x-request-id")
    details: Any = None
    try:
        body = response.json()
    except ValueError:
        body = None
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        code = str(error.get("code", code))
        message = str(error.get("message", message))
        request_id = error.get("request_id") or request_id
        details = error.get("details")
    error_class = error_class_for_status(response.status_code)
    return error_class(response.status_code, code, message, request_id, details)
