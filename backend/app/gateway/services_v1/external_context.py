from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from fastapi import Header, HTTPException
from pydantic import BaseModel

from deerflow.runtime.user_context import reset_current_user, set_current_user


class ExternalContext(BaseModel):
    app_id: str
    api_key: str
    request_id: str | None = None
    external_user_id: str | None = None


@dataclass(frozen=True)
class ExternalPrincipal:
    id: str


def _unauthorized(message: str, request_id: str | None = None) -> HTTPException:
    return HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": message, "request_id": request_id})


async def get_external_context(
    x_app_id: str | None = Header(default=None, alias="X-App-Id"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> AsyncIterator[ExternalContext]:
    if not x_app_id:
        raise _unauthorized("Missing X-App-Id header", x_request_id)
    if not x_api_key:
        raise _unauthorized("Missing X-API-Key header", x_request_id)
    context = ExternalContext(app_id=x_app_id, api_key=x_api_key, request_id=x_request_id, external_user_id=x_user_id)
    token = set_current_user(ExternalPrincipal(id=x_user_id or x_app_id))
    try:
        yield context
    finally:
        reset_current_user(token)


async def get_optional_context(
    x_app_id: str | None = Header(default=None, alias="X-App-Id"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> AsyncIterator[ExternalContext]:
    """Like ``get_external_context`` but does not require auth headers.

    If ``X-App-Id`` and ``X-API-Key`` are both provided, behaves exactly
    like ``get_external_context``. If either is missing, yields a public
    anonymous context instead of raising 401.

    This is useful for public download/preview endpoints where the URL
    itself is the authorization (shared artifact links).
    """
    if x_app_id and x_api_key:
        context = ExternalContext(app_id=x_app_id, api_key=x_api_key, request_id=x_request_id, external_user_id=x_user_id)
    else:
        context = ExternalContext(app_id="public", api_key="", request_id=x_request_id, external_user_id=x_user_id)
    token = set_current_user(ExternalPrincipal(id=x_user_id or context.app_id))
    try:
        yield context
    finally:
        reset_current_user(token)


def build_external_metadata(context: ExternalContext, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = dict(metadata or {})
    merged["app_id"] = context.app_id
    if context.external_user_id:
        merged["external_user_id"] = context.external_user_id
    if context.request_id:
        merged["request_id"] = context.request_id
    return merged


def inject_external_user(runtime_context: dict[str, Any], context: ExternalContext) -> dict[str, Any]:
    merged = dict(runtime_context)
    if context.external_user_id:
        merged.setdefault("user_id", context.external_user_id)
    return merged
