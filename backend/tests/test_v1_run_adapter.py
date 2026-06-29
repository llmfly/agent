from app.gateway.schemas.v1.conversations import ConversationMessageRequest, RunOptions
from app.gateway.services_v1.external_context import ExternalContext
from app.gateway.services_v1.run_adapter import build_run_create_request


def test_run_adapter_maps_external_message_request_to_run_create_request():
    prompt = "Summarize risk based on selected data sources."
    body = ConversationMessageRequest(
        agent_id="brand-agent",
        content=prompt,
        datasource_ids=["ds-1", "ds-2"],
        options=RunOptions(model="default", thinking_enabled=True, subagent_enabled=False, citation_required=True, max_context_tokens=8000),
        metadata={"project_id": "p-1"},
    )
    context = ExternalContext(app_id="app-1", api_key="key", request_id="req-1", external_user_id="user-1")

    run_body = build_run_create_request(body, context)

    assert run_body.assistant_id == "brand-agent"
    assert run_body.input == {"messages": [{"type": "human", "content": [{"type": "text", "text": prompt}]}]}
    assert run_body.metadata == {
        "project_id": "p-1",
        "datasource_ids": ["ds-1", "ds-2"],
        "app_id": "app-1",
        "external_user_id": "user-1",
        "request_id": "req-1",
    }
    assert run_body.context == {
        "mode": "flash",
        "model_name": "default",
        "thinking_enabled": True,
        "subagent_enabled": False,
        "citation_required": True,
        "max_context_tokens": 8000,
        "user_id": "user-1",
    }
    assert run_body.stream_mode == ["messages-tuple", "values", "updates", "custom", "events"]
    assert run_body.stream_subgraphs is True
    assert run_body.stream_resumable is True
    assert run_body.on_disconnect == "cancel"


def test_run_adapter_defaults_to_flash_mode_like_native_frontend():
    body = ConversationMessageRequest(agent_id="lead-agent", content="Hello")
    context = ExternalContext(app_id="app-1", api_key="key", request_id="req-1", external_user_id="user-1")

    run_body = build_run_create_request(body, context)

    assert run_body.context == {
        "mode": "flash",
        "thinking_enabled": False,
        "user_id": "user-1",
    }


def test_run_adapter_maps_mode_defaults_like_native_frontend():
    body = ConversationMessageRequest(agent_id="lead-agent", content="Think", options=RunOptions(mode="thinking"))
    context = ExternalContext(app_id="app-1", api_key="key", request_id="req-1", external_user_id="user-1")

    run_body = build_run_create_request(body, context)

    assert run_body.context["mode"] == "thinking"
    assert run_body.context["thinking_enabled"] is True
    assert run_body.context["reasoning_effort"] == "low"
