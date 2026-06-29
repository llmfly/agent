from unittest.mock import AsyncMock, MagicMock

from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from app.gateway.routers import v1
from app.gateway.services_v1.data_source_service import resolve_selected_data_sources
from deerflow.persistence.thread_meta.memory import MemoryThreadMetaStore


def _headers():
    return {"X-App-Id": "app", "X-API-Key": "key", "X-User-Id": "user-1", "X-Request-Id": "req-1"}


def _make_app():
    app = make_authed_test_app()
    store = InMemoryStore()
    app.state.store = store
    app.state.checkpointer = InMemorySaver()
    app.state.thread_store = MemoryThreadMetaStore(store)
    app.state.run_event_store = MagicMock()
    app.state.run_event_store.list_messages = AsyncMock(return_value=[])
    app.include_router(v1.router)
    return app


def test_register_and_list_data_sources():
    app = _make_app()

    with TestClient(app) as client:
        created = client.post("/api/v1/conversations", json={"title": "Data Chat"}, headers=_headers())
        conversation_id = created.json()["conversation_id"]

        response = client.post(
            f"/api/v1/conversations/{conversation_id}/data-sources",
            json={"type": "text", "name": "Policy", "content": "Selected source content", "metadata": {"kind": "policy"}},
            headers=_headers(),
        )
        assert response.status_code == 201, response.text
        datasource_id = response.json()["datasource_id"]

        listed = client.get(f"/api/v1/conversations/{conversation_id}/data-sources", headers=_headers())

    assert listed.status_code == 200, listed.text
    assert listed.json()["datasources"][0]["datasource_id"] == datasource_id
    assert listed.json()["datasources"][0]["metadata"] == {"kind": "policy"}


def test_resolve_selected_data_sources_preserves_order_and_applies_budget():
    app = _make_app()

    async def _resolve():
        from starlette.requests import Request

        scope = {"type": "http", "app": app, "headers": [], "method": "GET", "path": "/"}
        request = Request(scope)
        return await resolve_selected_data_sources(request, "conv-1", ["ds-2", "ds-1"], max_context_tokens=2)

    import asyncio

    selected = asyncio.run(_run_setup_and_resolve(app, _resolve))
    assert [source["datasource_id"] for source in selected] == ["ds-2", "ds-1"]
    assert selected[0]["content"] == "ghijkl"
    assert selected[1]["content"] == "abcdef"


async def _run_setup_and_resolve(app, resolve):
    from app.gateway.services_v1.external_context import ExternalPrincipal
    from deerflow.runtime.user_context import reset_current_user, set_current_user

    token = set_current_user(ExternalPrincipal(id="user-1"))
    try:
        await app.state.thread_store.create(
            "conv-1",
            metadata={
                "_v1_data_sources": [
                    {"datasource_id": "ds-1", "type": "text", "name": "A", "content": "abcdef", "metadata": {}},
                    {"datasource_id": "ds-2", "type": "text", "name": "B", "content": "ghijkl", "metadata": {}},
                ]
            },
        )
        return await resolve()
    finally:
        reset_current_user(token)
