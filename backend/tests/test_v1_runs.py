import asyncio
from unittest.mock import AsyncMock, MagicMock

from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient
from langgraph.store.memory import InMemoryStore

from app.gateway.routers import v1
from deerflow.persistence.thread_meta.memory import MemoryThreadMetaStore
from deerflow.runtime.runs.manager import RunManager


def test_get_and_cancel_run():
    app = make_authed_test_app()
    run_manager = RunManager()
    record = asyncio.run(run_manager.create("conv-1", "brand-agent", metadata={"app_id": "app"}))
    app.state.run_manager = run_manager
    app.include_router(v1.router)

    with TestClient(app) as client:
        get = client.get(f"/api/v1/runs/{record.run_id}", headers={"X-App-Id": "app", "X-API-Key": "key"})
        assert get.status_code == 200, get.text
        assert get.json()["conversation_id"] == "conv-1"
        assert get.json()["agent_id"] == "brand-agent"

        cancel = client.post(f"/api/v1/runs/{record.run_id}/cancel", json={"action": "interrupt"}, headers={"X-App-Id": "app", "X-API-Key": "key"})
        assert cancel.status_code == 200, cancel.text
        assert cancel.json()["status"] == "cancel_requested"


def test_v1_run_feedback_uses_run_thread_scope():
    app = make_authed_test_app()
    store = InMemoryStore()
    app.state.thread_store = MemoryThreadMetaStore(store)
    run_manager = RunManager()
    record = asyncio.run(run_manager.create("conv-1", "brand-agent", metadata={"app_id": "app"}))
    app.state.run_manager = run_manager
    app.state.run_store = MagicMock()
    app.state.run_store.get = AsyncMock(return_value={"run_id": record.run_id, "thread_id": "conv-1"})
    app.state.feedback_repo = MagicMock()
    app.state.feedback_repo.upsert = AsyncMock(
        return_value={
            "feedback_id": "fb-1",
            "run_id": record.run_id,
            "thread_id": "conv-1",
            "user_id": "user-1",
            "message_id": None,
            "rating": 1,
            "comment": None,
            "created_at": "t1",
        }
    )
    app.state.feedback_repo.delete_by_run = AsyncMock(return_value=True)
    app.include_router(v1.router)

    headers = {"X-App-Id": "app", "X-API-Key": "key", "X-User-Id": "user-1"}
    with TestClient(app) as client:
        put = client.put(f"/api/v1/runs/{record.run_id}/feedback", json={"rating": 1}, headers=headers)
        assert put.status_code == 200, put.text
        assert put.json()["feedback_id"] == "fb-1"
        app.state.feedback_repo.upsert.assert_awaited_once()
        assert app.state.feedback_repo.upsert.await_args.kwargs["thread_id"] == "conv-1"
        assert app.state.feedback_repo.upsert.await_args.kwargs["user_id"] == "user-1"

        delete = client.delete(f"/api/v1/runs/{record.run_id}/feedback", headers=headers)
        assert delete.status_code == 200, delete.text
        assert delete.json() == {"success": True}
