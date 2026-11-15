"""Request dependencies: application context and authentication."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Header, Request

from quantum_platform.api.errors import ApiError
from quantum_platform.execution.service import ExecutionService
from quantum_platform.settings import Settings
from quantum_platform.storage.base import ExperimentRepository


@dataclass
class AppContext:
    settings: Settings
    repo: ExperimentRepository
    service: ExecutionService
    clock: Callable[[], datetime]
    id_factory: Callable[[], str]


def get_context(request: Request) -> AppContext:
    context: AppContext = request.app.state.context
    return context


Context = Annotated[AppContext, Depends(get_context)]


def require_owner(context: Context, x_api_key: Annotated[str | None, Header()] = None) -> str:
    """Authenticate the caller and return the owner the API key belongs to."""
    if not x_api_key:
        raise ApiError(401, "missing_api_key", "The X-API-Key header is required.")
    owner = context.settings.api_keys.get(x_api_key)
    if owner is None:
        raise ApiError(401, "invalid_api_key", "The API key is not recognised.")
    return owner


Owner = Annotated[str, Depends(require_owner)]
