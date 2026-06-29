from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.gateway.schemas.v1.conversations import ConversationMessageRequest, ConversationMessageResponse


class AgentDTO(BaseModel):
    agent_id: str
    name: str
    type: Literal["system", "custom"]
    description: str = ""
    model: str | None = None
    skills: list[str] | None = None
    tool_groups: list[str] | None = None
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentListResponse(BaseModel):
    agents: list[AgentDTO]


class AgentInvokeRequest(ConversationMessageRequest):
    pass


class AgentInvokeResponse(ConversationMessageResponse):
    pass
