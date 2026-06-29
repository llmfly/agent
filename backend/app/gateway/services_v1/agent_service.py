from __future__ import annotations

from app.gateway.schemas.v1.agents import AgentDTO, AgentListResponse
from deerflow.config.agents_config import list_custom_agents


def list_available_agents() -> AgentListResponse:
    agents = [
        AgentDTO(
            agent_id="lead-agent",
            name="General Agent",
            type="system",
            description="General-purpose conversation and task agent.",
        )
    ]
    try:
        for cfg in list_custom_agents():
            agents.append(
                AgentDTO(
                    agent_id=cfg.name,
                    name=cfg.name,
                    type="custom",
                    description=cfg.description or "",
                    model=cfg.model,
                    skills=cfg.skills,
                    tool_groups=cfg.tool_groups,
                )
            )
    except Exception:
        pass
    return AgentListResponse(agents=agents)
