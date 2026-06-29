"""Common DTOs for v1 external API."""

from __future__ import annotations

from typing import Any, Literal
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ErrorDTO(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Unified error response for v1 API."""

    success: bool = False
    error: ErrorDTO
    request_id: str | None = None


class SuccessResponse(BaseModel):
    """Unified success wrapper."""

    success: bool = True
    data: Any = None
    request_id: str | None = None


class UsageInfo(BaseModel):
    """Token usage info."""
class PaginationDTO(BaseModel):
    limit: int
    offset: int | None = None
    has_more: bool = False


class UsageDTO(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class PaginationParams(BaseModel):
    """Pagination query parameters."""
    limit: int = Field(default=20, ge=1, le=100, description="Items per page")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")

class MessageDTO(BaseModel):
    message_id: str | None = None
    run_id: str | None = None
    role: Literal["user", "assistant", "tool", "system"]
    content: str | list[dict[str, Any]]
    created_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactDTO(BaseModel):
    artifact_id: str
    conversation_id: str | None = None
    run_id: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    url: str
    created_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class PaginatedResponse(BaseModel):
    """Generic paginated response."""

    items: list[Any]
    total: int
    limit: int
    offset: int
class RunDTO(BaseModel):
    run_id: str
    conversation_id: str
    agent_id: str | None = None
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    usage: UsageDTO = Field(default_factory=UsageDTO)
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
