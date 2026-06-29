from unittest.mock import patch

from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.routers import v1


def test_list_agents_includes_system_and_custom_without_soul():
    app = make_authed_test_app()
    app.include_router(v1.router)

    with patch("app.gateway.services_v1.agent_service.list_custom_agents") as list_custom:
        custom = type("AgentConfigStub", (), {"name": "brand-agent", "description": "Brand", "model": None, "skills": ["brand"], "tool_groups": ["web"]})()
        list_custom.return_value = [custom]
        with TestClient(app) as client:
            response = client.get("/api/v1/agents", headers={"X-App-Id": "app", "X-API-Key": "key"})

    assert response.status_code == 200, response.text
    agents = response.json()["agents"]
    assert any(agent["agent_id"] == "lead-agent" and agent["type"] == "system" for agent in agents)
    brand = next(agent for agent in agents if agent["agent_id"] == "brand-agent")
    assert brand["description"] == "Brand"
    assert "soul" not in brand
