import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from app.gateway.routers import v1
from deerflow.persistence.thread_meta.memory import MemoryThreadMetaStore
from deerflow.runtime import DisconnectMode, MemoryStreamBridge, RunStatus


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


def test_create_get_patch_list_delete_conversation():
    app = _make_app()

    with TestClient(app) as client:
        create = client.post(
            "/api/v1/conversations",
            json={"agent_id": "brand-agent", "title": "Brand Chat", "metadata": {"project_id": "p1"}},
            headers=_headers(),
        )
        assert create.status_code == 200, create.text
        conversation_id = create.json()["conversation_id"]
        assert create.json()["title"] == "Brand Chat"

        get = client.get(f"/api/v1/conversations/{conversation_id}", headers=_headers())
        assert get.status_code == 200, get.text
        assert get.json()["conversation_id"] == conversation_id
        assert "values" not in get.json()

        patch = client.patch(f"/api/v1/conversations/{conversation_id}", json={"title": "Renamed"}, headers=_headers())
        assert patch.status_code == 200, patch.text
        assert patch.json()["title"] == "Renamed"

        listed = client.get("/api/v1/conversations", headers=_headers())
        assert listed.status_code == 200, listed.text
        assert listed.json()["items"][0]["conversation_id"] == conversation_id

        delete = client.delete(f"/api/v1/conversations/{conversation_id}", headers=_headers())
        assert delete.status_code == 204


def test_search_conversations_filters_by_metadata():
    app = _make_app()

    with TestClient(app) as client:
        create = client.post(
            "/api/v1/conversations",
            json={"title": "Brand Chat", "metadata": {"project_id": "p1"}},
            headers=_headers(),
        )
        assert create.status_code == 200, create.text

        found = client.post(
            "/api/v1/conversations/search",
            json={"metadata": {"project_id": "p1"}, "limit": 10},
            headers=_headers(),
        )
        assert found.status_code == 200, found.text
        assert found.json()["items"][0]["metadata"]["project_id"] == "p1"


def test_list_conversation_messages_normalizes_roles():
    app = _make_app()
    app.state.run_event_store.list_messages = AsyncMock(
        return_value=[
            {"id": "m1", "run_id": "r1", "event_type": "human_message", "content": "hi", "created_at": "t1"},
            {"id": "m2", "run_id": "r1", "event_type": "ai_message", "content": "hello", "created_at": "t2"},
        ]
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/conversations/conv-1/messages", headers=_headers())

    assert response.status_code == 200, response.text
    assert response.json()["items"] == [
        {"message_id": "m1", "run_id": "r1", "role": "user", "content": "hi", "created_at": "t1", "metadata": {}},
        {"message_id": "m2", "run_id": "r1", "role": "assistant", "content": "hello", "created_at": "t2", "metadata": {}},
    ]


def test_v1_conversation_state_history_run_messages_and_token_usage():
    app = _make_app()
    app.state.run_event_store.list_messages_by_run = AsyncMock(
        return_value=[
            {"seq": 1, "id": "m1", "run_id": "run-1", "event_type": "human_message", "content": "hi", "created_at": "t1"},
            {"seq": 2, "id": "m2", "run_id": "run-1", "event_type": "ai_message", "content": "hello", "created_at": "t2"},
        ]
    )
    app.state.run_store = MagicMock()
    app.state.run_store.aggregate_tokens_by_thread = AsyncMock(
        return_value={
            "total_tokens": 12,
            "total_input_tokens": 5,
            "total_output_tokens": 7,
            "total_runs": 1,
            "by_model": {},
            "by_caller": {},
        }
    )

    with TestClient(app) as client:
        create = client.post("/api/v1/conversations", json={"title": "Chat"}, headers=_headers())
        assert create.status_code == 200, create.text
        conversation_id = create.json()["conversation_id"]

        state = client.get(f"/api/v1/conversations/{conversation_id}/state", headers=_headers())
        assert state.status_code == 200, state.text
        assert "values" in state.json()

        patched = client.patch(
            f"/api/v1/conversations/{conversation_id}/state",
            json={"values": {"title": "Renamed"}},
            headers=_headers(),
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["values"]["title"] == "Renamed"

        history = client.get(f"/api/v1/conversations/{conversation_id}/history?limit=1", headers=_headers())
        assert history.status_code == 200, history.text
        assert isinstance(history.json(), list)

        messages = client.get(f"/api/v1/conversations/{conversation_id}/runs/run-1/messages?limit=1", headers=_headers())
        assert messages.status_code == 200, messages.text
        assert messages.json()["data"][0]["id"] == "m2"
        assert messages.json()["has_more"] is True

        usage = client.get(f"/api/v1/conversations/{conversation_id}/token-usage", headers=_headers())
        assert usage.status_code == 200, usage.text
        assert usage.json()["thread_id"] == conversation_id
        assert usage.json()["total_tokens"] == 12


def test_v1_conversation_run_lifecycle_delegates_to_thread_runs(monkeypatch):
    app = _make_app()
    calls = []

    async def fake_create_run(thread_id, body, request):
        calls.append(("create", thread_id, body.input))
        return {"run_id": "run-1", "thread_id": thread_id, "status": "pending"}

    async def fake_wait_run(thread_id, body, request):
        calls.append(("wait", thread_id, body.input))
        return {"messages": []}

    async def fake_get_run(thread_id, run_id, request):
        calls.append(("get", thread_id, run_id))
        return {"run_id": run_id, "thread_id": thread_id, "status": "running"}

    async def fake_cancel_run(thread_id, run_id, request, wait=False, action="interrupt"):
        calls.append(("cancel", thread_id, run_id, wait, action))
        return {"status_code": 202}

    async def fake_list_events(thread_id, run_id, request, event_types=None, limit=500):
        calls.append(("events", thread_id, run_id, event_types, limit))
        return [{"event": "metadata"}]

    monkeypatch.setattr("app.gateway.routers.v1.conversations.create_thread_run", fake_create_run)
    monkeypatch.setattr("app.gateway.routers.v1.conversations.wait_thread_run", fake_wait_run)
    monkeypatch.setattr("app.gateway.routers.v1.conversations.get_thread_run", fake_get_run)
    monkeypatch.setattr("app.gateway.routers.v1.conversations.cancel_thread_run", fake_cancel_run)
    monkeypatch.setattr("app.gateway.routers.v1.conversations.list_thread_run_events", fake_list_events)

    with TestClient(app) as client:
        create = client.post(
            "/api/v1/conversations/conv-1/runs",
            json={"input": {"messages": []}},
            headers=_headers(),
        )
        wait = client.post(
            "/api/v1/conversations/conv-1/runs/wait",
            json={"input": {"messages": []}},
            headers=_headers(),
        )
        get = client.get("/api/v1/conversations/conv-1/runs/run-1", headers=_headers())
        cancel = client.post("/api/v1/conversations/conv-1/runs/run-1/cancel?wait=1&action=rollback", headers=_headers())
        events = client.get("/api/v1/conversations/conv-1/runs/run-1/events?event_types=metadata&limit=10", headers=_headers())

    assert create.status_code == 200, create.text
    assert wait.status_code == 200, wait.text
    assert get.status_code == 200, get.text
    assert cancel.status_code == 200, cancel.text
    assert events.status_code == 200, events.text
    assert calls == [
        ("create", "conv-1", {"messages": []}),
        ("wait", "conv-1", {"messages": []}),
        ("get", "conv-1", "run-1"),
        ("cancel", "conv-1", "run-1", True, "rollback"),
        ("events", "conv-1", "run-1", "metadata", 10),
    ]


def test_v1_conversation_suggestions_delegates_to_existing_generator(monkeypatch):
    app = _make_app()

    async def fake_generate_suggestions(thread_id, body, request, config):
        assert thread_id == "conv-1"
        assert body.n == 2
        return {"suggestions": ["next question?"]}

    monkeypatch.setattr("app.gateway.routers.v1.conversations.generate_thread_suggestions", fake_generate_suggestions)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/conversations/conv-1/suggestions",
            json={"messages": [{"role": "user", "content": "hi"}], "n": 2},
            headers=_headers(),
        )

    assert response.status_code == 200, response.text
    assert response.json() == {"suggestions": ["next question?"]}


def test_v1_stream_emits_run_completed_on_bridge_end(monkeypatch):
    monkeypatch.setenv("V1_CONVERSATION_STREAM_USE_THREAD_PROXY", "0")
    app = _make_app()
    app.state.stream_bridge = MemoryStreamBridge()
    app.state.run_manager = MagicMock()
    app.state.run_manager.cancel = AsyncMock()

    async def fake_fetch_and_sync_data_sources(conversation_id, request):
        return None

    async def fake_resolve_selected_data_sources(*args, **kwargs):
        return []

    async def fake_sync_artifacts_from_checkpoint(request, conversation_id, run_id):
        return None

    async def fake_start_run(body, conversation_id, request):
        await app.state.stream_bridge.publish("run-1", "metadata", {"run_id": "run-1", "thread_id": conversation_id})
        await app.state.stream_bridge.publish("run-1", "messages", ["hello", {}])
        await app.state.stream_bridge.publish_end("run-1")
        return SimpleNamespace(
            run_id="run-1",
            status=RunStatus.success,
            on_disconnect=DisconnectMode.cancel,
        )

    monkeypatch.setattr("app.gateway.routers.v1.conversations.starfish_service.fetch_and_sync_data_sources", fake_fetch_and_sync_data_sources)
    monkeypatch.setattr("app.gateway.routers.v1.conversations.resolve_selected_data_sources", fake_resolve_selected_data_sources)
    monkeypatch.setattr("app.gateway.routers.v1.conversations.sync_artifacts_from_checkpoint", fake_sync_artifacts_from_checkpoint)
    monkeypatch.setattr("app.gateway.routers.v1.conversations.start_run", fake_start_run)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/conversations/conv-1/stream",
            json={"agent_id": "lead_agent", "content": "hello"},
            headers=_headers(),
        )

    assert response.status_code == 200, response.text
    assert "event: run.started" in response.text
    assert "event: message.delta" in response.text
    assert "event: run.completed" in response.text
    app.state.run_manager.cancel.assert_not_awaited()


def test_v1_direct_stream_uses_wall_clock_timeout(monkeypatch):
    monkeypatch.setenv("V1_CONVERSATION_STREAM_USE_THREAD_PROXY", "0")
    monkeypatch.setenv("V1_CONVERSATION_STREAM_TIMEOUT_SECONDS", "0.01")
    app = _make_app()
    app.state.stream_bridge = MemoryStreamBridge()
    app.state.run_manager = MagicMock()
    record = SimpleNamespace(
        run_id="run-1",
        status=RunStatus.running,
        on_disconnect=DisconnectMode.cancel,
    )

    async def fake_cancel(run_id):
        record.status = RunStatus.interrupted
        return True

    app.state.run_manager.cancel = AsyncMock(side_effect=fake_cancel)

    async def fake_fetch_and_sync_data_sources(conversation_id, request):
        return None

    async def fake_resolve_selected_data_sources(*args, **kwargs):
        return []

    async def fake_start_run(body, conversation_id, request):
        await app.state.stream_bridge.publish("run-1", "metadata", {"run_id": "run-1", "thread_id": conversation_id})
        return record

    monkeypatch.setattr("app.gateway.routers.v1.conversations.starfish_service.fetch_and_sync_data_sources", fake_fetch_and_sync_data_sources)
    monkeypatch.setattr("app.gateway.routers.v1.conversations.resolve_selected_data_sources", fake_resolve_selected_data_sources)
    monkeypatch.setattr("app.gateway.routers.v1.conversations.start_run", fake_start_run)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/conversations/conv-1/stream",
            json={"agent_id": "lead_agent", "content": "hello"},
            headers=_headers(),
        )

    assert response.status_code == 200, response.text
    assert "event: run.started" in response.text
    assert "event: run.failed" in response.text
    assert '"code": "RUN_TIMEOUT"' in response.text
    app.state.run_manager.cancel.assert_awaited_once_with("run-1")


def test_v1_stream_extracts_run_id_from_content_location():
    from app.gateway.routers.v1.conversations import _extract_run_id_from_content_location

    assert _extract_run_id_from_content_location("/api/threads/thread-1/runs/run-1") == "run-1"
    assert _extract_run_id_from_content_location("/api/threads/thread-1/runs/run-1?x=1") == "run-1"
    assert _extract_run_id_from_content_location(None) is None


def test_v1_stream_defaults_to_direct_run_mode(monkeypatch):
    from app.gateway.routers.v1.conversations import _use_thread_stream_proxy

    monkeypatch.delenv("V1_CONVERSATION_STREAM_USE_THREAD_PROXY", raising=False)

    assert _use_thread_stream_proxy() is False


def test_v1_proxied_stream_uses_wall_clock_timeout(monkeypatch):
    monkeypatch.setenv("V1_CONVERSATION_STREAM_USE_THREAD_PROXY", "1")
    monkeypatch.setenv("V1_CONVERSATION_STREAM_TIMEOUT_SECONDS", "0.05")
    app = _make_app()
    cancel_calls = []

    async def fake_fetch_and_sync_data_sources(conversation_id, request):
        return None

    async def fake_resolve_selected_data_sources(*args, **kwargs):
        return []

    class FakeStreamResponse:
        status_code = 200
        headers = {"Content-Location": "/api/threads/conv-1/runs/run-timeout"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def aread(self):
            return b""

        async def aiter_lines(self):
            while True:
                await asyncio.sleep(0.2)
                yield ": heartbeat"

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, *args, **kwargs):
            return FakeStreamResponse()

        async def post(self, url, *args, **kwargs):
            cancel_calls.append(url)
            return SimpleNamespace(status_code=202)

    monkeypatch.setattr("app.gateway.routers.v1.conversations.starfish_service.fetch_and_sync_data_sources", fake_fetch_and_sync_data_sources)
    monkeypatch.setattr("app.gateway.routers.v1.conversations.resolve_selected_data_sources", fake_resolve_selected_data_sources)
    monkeypatch.setattr("app.gateway.routers.v1.conversations.httpx.AsyncClient", FakeAsyncClient)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/conversations/conv-1/stream",
            json={"agent_id": "lead_agent", "content": "hello"},
            headers=_headers(),
        )

    assert response.status_code == 200, response.text
    assert "event: run.started" in response.text
    assert "event: run.failed" in response.text
    assert '"code": "RUN_TIMEOUT"' in response.text
    assert any("/api/threads/conv-1/runs/run-timeout/cancel" in url for url in cancel_calls)
