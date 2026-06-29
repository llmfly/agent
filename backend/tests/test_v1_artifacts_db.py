from unittest.mock import AsyncMock, MagicMock

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.routers import v1
from app.gateway.services_v1.artifact_service import artifact_service
from app.gateway.services_v1.conversation_service import create_conversation, get_conversation
from app.gateway.services_v1.external_context import ExternalContext
from deerflow.persistence.engine import close_engine, get_session_factory, init_engine
from deerflow.persistence.thread_meta.sql import ThreadMetaRepository


def _headers():
    return {"X-App-Id": "app", "X-API-Key": "key", "X-User-Id": "user-1", "X-Request-Id": "req-1"}

@pytest.fixture
async def db_setup(tmp_path):
    # Reset cached session factory on singleton to prevent cross-test database contamination
    artifact_service._session_factory = None
    # Initialize a temporary SQLite database
    url = f"sqlite+aiosqlite:///{tmp_path / 'test_artifacts.db'}"
    await init_engine("sqlite", url=url, sqlite_dir=str(tmp_path))
    yield get_session_factory()
    await close_engine()
    artifact_service._session_factory = None

@pytest.mark.anyio
async def test_artifact_persistence_and_enrichment(db_setup, tmp_path):
    sf = db_setup
    
    # Setup conversation record in SQLite to satisfy foreign key
    thread_store = ThreadMetaRepository(sf)
    conv_id = "conv_test_1"
    await thread_store.create(
        conv_id, 
        assistant_id="brand-agent", 
        display_name="测试会话", 
        metadata={"app_id": "app", "external_user_id": "user-1"}
    )
    
    # 1. Test direct database operations via artifact_service
    art_id = await artifact_service.create_artifact(
        conversation_id=conv_id,
        name="测试报告",
        artifact_type="report",
        meta_json={"test_key": "test_val"}
    )
    assert art_id.startswith("art_")
    
    # Add files
    file_id_docx = await artifact_service.add_artifact_file(
        artifact_id=art_id,
        file_format="docx",
        filename="report.docx",
        file_path=str(tmp_path / "report.docx"),
        download_url="/api/v1/artifacts/art_file_docx_1",
        file_id="art_file_docx_1"
    )
    assert file_id_docx == "art_file_docx_1"
    
    file_id_html = await artifact_service.add_artifact_file(
        artifact_id=art_id,
        file_format="html",
        filename="report.html",
        file_path=str(tmp_path / "report.html"),
        download_url="/api/v1/artifacts/art_file_html_1",
        file_id="art_file_html_1"
    )
    assert file_id_html == "art_file_html_1"
    
    # Update status to success
    await artifact_service.update_artifact_status(art_id, "success", meta_json={"summary": "生成成功"})
    
    # Get artifact and assert
    art = await artifact_service.get_artifact(art_id)
    assert art is not None
    assert art.name == "测试报告"
    assert art.status == "success"
    assert art.meta_json["summary"] == "生成成功"
    assert len(art.files) == 2
    assert {f.file_format for f in art.files} == {"docx", "html"}
    
    # Get file by ID
    file_record = await artifact_service.get_artifact_file("art_file_docx_1")
    assert file_record is not None
    assert file_record.filename == "report.docx"

    # List conversation artifacts
    arts = await artifact_service.list_conversation_artifacts(conv_id)
    assert len(arts) == 1
    assert arts[0].artifact_id == art_id

    # 2. Test metadata enrichment in conversation service
    context = ExternalContext(app_id="app", api_key="key", external_user_id="user-1")
    req = MagicMock()
    req.app.state.thread_store = thread_store
    req.app.state.checkpointer = AsyncMock()
    
    conv_dto = await create_conversation(req, MagicMock(agent_id="brand-agent", title="Brand Chat", metadata={}), context)
    conv_id_2 = conv_dto.conversation_id
    
    # Bind artifact to the newly created conversation
    art_id_2 = await artifact_service.create_artifact(
        conversation_id=conv_id_2,
        name="测试报告2",
        artifact_type="report",
        artifact_id="rep_test_2"
    )
    await artifact_service.add_artifact_file(
        artifact_id=art_id_2,
        file_format="docx",
        filename="report2.docx",
        file_path=str(tmp_path / "report2.docx"),
        download_url="/api/v1/artifacts/art_file_docx_2",
        file_id="art_file_docx_2"
    )
    await artifact_service.update_artifact_status(art_id_2, "success")
    
    # Retrieve the conversation and check that metadata is enriched with the artifact
    enriched_conv = await get_conversation(req, conv_id_2)
    assert "_v1_artifacts" in enriched_conv.metadata
    v1_arts = enriched_conv.metadata["_v1_artifacts"]
    assert len(v1_arts) == 1
    assert v1_arts[0]["artifact_id"] == art_id_2
    assert v1_arts[0]["name"] == "测试报告2"
    assert v1_arts[0]["status"] == "success"
    assert len(v1_arts[0]["files"]) == 1
    assert v1_arts[0]["files"][0]["file_id"] == "art_file_docx_2"
    assert v1_arts[0]["files"][0]["format"] == "docx"

@pytest.mark.anyio
async def test_artifacts_router_endpoints(db_setup, tmp_path):
    sf = db_setup
    
    # Setup test app
    app = make_authed_test_app()
    app.state.store = MagicMock()
    app.state.checkpointer = MagicMock()
    app.state.thread_store = ThreadMetaRepository(sf)
    app.state.run_event_store = MagicMock()
    app.state.run_event_store.list_messages = AsyncMock(return_value=[])
    app.include_router(v1.router)
    
    # Create conversation and artifact in DB
    context = ExternalContext(app_id="app", api_key="key", external_user_id="user-1")
    req = MagicMock()
    req.app.state.thread_store = app.state.thread_store
    req.app.state.checkpointer = AsyncMock()
    
    conv_dto = await create_conversation(req, MagicMock(agent_id="brand-agent", title="Brand Chat", metadata={}), context)
    conv_id = conv_dto.conversation_id
    
    # Create report artifact
    art_id = await artifact_service.create_artifact(
        conversation_id=conv_id,
        name="Diabetes Report",
        artifact_type="report",
        artifact_id="rep_diabetes_1"
    )
    
    # Create fake physical docx file
    dummy_file = tmp_path / "diabetes_report.docx"
    dummy_file.write_bytes(b"dummy docx content")
    
    file_id = await artifact_service.add_artifact_file(
        artifact_id=art_id,
        file_format="docx",
        filename="diabetes_report.docx",
        file_path=str(dummy_file),
        download_url="/api/v1/artifacts/art_file_docx_diabetes",
        file_id="art_file_docx_diabetes"
    )
    await artifact_service.update_artifact_status(art_id, "success")
    
    # Test GET /api/v1/conversations/{conversation_id}/artifacts via client
    with TestClient(app) as client:
        # Get artifacts list
        res = client.get(f"/api/v1/conversations/{conv_id}/artifacts", headers=_headers())
        assert res.status_code == 200, res.text
        data = res.json()
        assert len(data) == 1
        assert data[0]["artifact_id"] == file_id
        assert data[0]["filename"] == "diabetes_report.docx"
        assert data[0]["url"] == f"/api/v1/artifacts/{file_id}"
        assert data[0]["metadata"]["name"] == "Diabetes Report"
        assert data[0]["metadata"]["status"] == "success"
        
        # Test download endpoint: GET /api/v1/artifacts/{file_id}/download
        res_dl = client.get(f"/api/v1/artifacts/{file_id}/download", headers=_headers())
        assert res_dl.status_code == 200, res_dl.text
        assert res_dl.content == b"dummy docx content"
        assert "attachment" in res_dl.headers.get("content-disposition", "")
        assert "diabetes_report.docx" in res_dl.headers.get("content-disposition", "")


def test_v1_conversation_artifact_by_path_delegates_to_thread_artifact(monkeypatch):
    app = make_authed_test_app()
    app.include_router(v1.router)

    async def fake_get_thread_artifact(thread_id, path, request, download=False):
        from fastapi.responses import PlainTextResponse

        assert thread_id == "conv-1"
        assert path == "mnt/user-data/outputs/report.txt"
        assert download is True
        return PlainTextResponse("artifact")

    monkeypatch.setattr("app.gateway.routers.v1.conversations.get_thread_artifact", fake_get_thread_artifact)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/conversations/conv-1/artifacts/by-path/mnt/user-data/outputs/report.txt?download=true",
            headers=_headers(),
        )

    assert response.status_code == 200, response.text
    assert response.text == "artifact"
