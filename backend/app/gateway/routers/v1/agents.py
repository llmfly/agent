from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request

from app.gateway.routers.v1.conversations import stream_message_endpoint
from app.gateway.schemas.v1.agents import AgentInvokeRequest, AgentInvokeResponse, AgentListResponse
from app.gateway.schemas.v1.conversations import ConversationMessageRequest
from app.gateway.services_v1.agent_service import list_available_agents
from app.gateway.services_v1.conversation_service import send_message
from app.gateway.services_v1.external_context import ExternalContext, get_external_context

router = APIRouter(prefix="/agents", tags=["v1-agents"])


@router.get("", response_model=AgentListResponse, summary="List agents", description="List system and custom agents available to external callers.")
async def list_agents_endpoint(context: ExternalContext = Depends(get_external_context)) -> AgentListResponse:
    return list_available_agents()


@router.post("/{agent_id}/invoke", response_model=AgentInvokeResponse, summary="Invoke agent")
async def invoke_agent_endpoint(
    agent_id: str,
    body: AgentInvokeRequest,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
) -> AgentInvokeResponse:
    conversation_id = str(uuid.uuid4())
    msg = ConversationMessageRequest(
        agent_id=agent_id,
        content=body.content,
        datasource_ids=body.datasource_ids,
        options=body.options,
        metadata=body.metadata,
    )
    return await send_message(request, conversation_id, msg, context)


@router.post("/{agent_id}/stream", summary="Stream agent", description="Stream an agent response using a temporary conversation.")
async def stream_agent_endpoint(agent_id: str, body: AgentInvokeRequest, request: Request, context: ExternalContext = Depends(get_external_context)):
    conversation_id = str(uuid.uuid4())
    msg = ConversationMessageRequest(**body.model_dump(exclude={"agent_id"}), agent_id=agent_id)
    return await stream_message_endpoint(conversation_id, msg, request, context)
