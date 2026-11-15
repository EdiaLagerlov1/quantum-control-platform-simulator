"""Request context: request ID, correlation ID, API version header and access log."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from quantum_platform import API_VERSION
from quantum_platform.api.errors import error_response
from quantum_platform.logging_config import correlation_id_var, request_id_var

logger = logging.getLogger(__name__)

_MAX_ID_LENGTH = 128


def _client_id(value: str | None) -> str | None:
    """Accept a caller-supplied ID only if it is short and printable."""
    if value and len(value) <= _MAX_ID_LENGTH and value.isascii() and value.isprintable():
        return value
    return None


def install_request_context(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _client_id(request.headers.get("x-request-id")) or uuid.uuid4().hex
        correlation_id = _client_id(request.headers.get("x-correlation-id")) or request_id
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id
        request_token = request_id_var.set(request_id)
        correlation_token = correlation_id_var.set(correlation_id)
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                logger.exception("unhandled error")
                response = error_response(
                    request, 500, "internal_error", "An unexpected error occurred."
                )
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-API-Version"] = API_VERSION
            logger.info(
                "request handled",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                },
            )
            return response
        finally:
            request_id_var.reset(request_token)
            correlation_id_var.reset(correlation_token)
