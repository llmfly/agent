from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.gateway.schemas.v1.common import ArtifactDTO, MessageDTO, PaginationDTO, RunDTO, UsageDTO


class RunOptions(BaseModel):
    model: str | None = None
    mode: str | None = None
    thinking_enabled: bool | None = None
    reasoning_effort: str | None = None
    subagent_enabled: bool | None = None
    max_concurrent_subagents: int | None = None
    citation_required: bool | None = None
    max_context_tokens: int | None = None


class ConversationCreateRequest(BaseModel):
    agent_id: str | None = None
    title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationUpdateRequest(BaseModel):
    title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationSearchRequest(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    status: str | None = None


class ConversationDTO(BaseModel):
    conversation_id: str
    agent_id: str | None = None
    title: str | None = None
    status: str = "idle"
    last_message: MessageDTO | None = None
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationListResponse(BaseModel):
    items: list[ConversationDTO]
    pagination: PaginationDTO


class ConversationMessageRequest(BaseModel):
    agent_id: str | None = None
    content: str
    datasource_ids: list[str] = Field(default_factory=list)
    options: RunOptions = Field(default_factory=RunOptions)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationMessageResponse(BaseModel):
    run_id: str
    conversation_id: str
    agent_id: str | None = None
    status: str
    message: MessageDTO | None = None
    artifacts: list[ArtifactDTO] = Field(default_factory=list)
    usage: UsageDTO = Field(default_factory=UsageDTO)


class ConversationMessagesResponse(BaseModel):
    conversation_id: str
    items: list[MessageDTO]
    pagination: PaginationDTO


class ConversationRunsResponse(BaseModel):
    conversation_id: str
    items: list[RunDTO]
