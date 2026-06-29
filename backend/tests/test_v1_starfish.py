import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from starlette.requests import Request

from app.gateway.services_v1.starfish_service import starfish_service
from app.gateway.services_v1.data_source_service import _data_sources
from _router_auth_helpers import make_authed_test_app
from langgraph.store.memory import InMemoryStore
from langgraph.checkpoint.memory import InMemorySaver
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
    return app


@pytest.mark.asyncio
async def test_starfish_sync():
    app = _make_app()

    # 1. Create a conversation in the thread store first
    from app.gateway.services_v1.external_context import ExternalPrincipal
    from deerflow.runtime.user_context import reset_current_user, set_current_user

    token = set_current_user(ExternalPrincipal(id="user-1"))
    try:
        await app.state.thread_store.create(
            "conv-starfish",
            metadata={}
        )
    finally:
        reset_current_user(token)

    # 2. Prepare mock starfish data
    mock_starfish_response = {
        "msg": "操作成功",
        "code": 200,
        "data": [
            {
                "sourceId": "mysql-1",
                "sourceName": "本地测试MySQL",
                "sourceType": "DATABASE",
                "sourceConfig": {
                    "databaseType": "MYSQL",
                    "password": "pass",
                    "databaseName": "dip_node",
                    "port": 3306,
                    "host": "127.0.0.1",
                    "username": "root"
                },
                "tables": [
                    {
                        "tableId": "t1",
                        "tableName": "data_source"
                    }
                ]
            },
            {
                "sourceId": "file-2",
                "sourceName": "本地测试File",
                "sourceType": "FILE",
                "sourceConfig": {
                    "path": "/tmp/test.pdf",
                    "fileName": "test.pdf"
                }
            }
        ]
    }

    # 3. Create a mock request
    scope = {"type": "http", "app": app, "headers": [], "method": "POST", "path": "/"}
    request = Request(scope)

    # 4. Mock the HTTP response of httpx.AsyncClient.get
    class MockResponse:
        def __init__(self, json_data, status_code):
            self._json_data = json_data
            self.status_code = status_code

        def json(self):
            return self._json_data

    mock_get = AsyncMock(return_value=MockResponse(mock_starfish_response, 200))

    # Clear in-memory cache for this conversation first
    if "conv-starfish" in _data_sources:
        del _data_sources["conv-starfish"]

    mock_connect = MagicMock()
    mock_exists = MagicMock(return_value=True)

    with patch("httpx.AsyncClient.get", mock_get), \
         patch("pymysql.connect", mock_connect), \
         patch("os.path.exists", mock_exists):
        token = set_current_user(ExternalPrincipal(id="user-1"))
        try:
            await starfish_service.fetch_and_sync_data_sources("conv-starfish", request)
        finally:
            reset_current_user(token)

    # 5. Verify HTTP request was made with correct URL
    expected_url = starfish_service.api_url_template.format(conversation_id="conv-starfish")
    mock_get.assert_called_once_with(expected_url)

    # 6. Verify in-memory store was populated
    assert "conv-starfish" in _data_sources
    records = _data_sources["conv-starfish"]
    assert len(records) == 2

    # Check mysql record
    mysql_rec = next(r for r in records if r.datasource_id == "mysql-1")
    assert mysql_rec.type == "sql"
    assert mysql_rec.name == "本地测试MySQL"
    assert mysql_rec.content == "[SQL] mysql://127.0.0.1:3306/dip_node"
    assert mysql_rec.metadata["db_type"] == "mysql"
    assert mysql_rec.metadata["tables"] == ["data_source"]

    # Check file record
    file_rec = next(r for r in records if r.datasource_id == "file-2")
    assert file_rec.type == "file"
    assert file_rec.name == "本地测试File"
    assert file_rec.content == "[File] /tmp/test.pdf"

    # 7. Verify SQLite thread store does NOT store the credentials (zero persistence)
    token = set_current_user(ExternalPrincipal(id="user-1"))
    try:
        thread_record = await app.state.thread_store.get("conv-starfish")
        metadata = thread_record.get("metadata") or {}
        v1_sources = metadata.get("_v1_data_sources") or []
        assert len(v1_sources) == 0  # No database connection credentials stored on disk!

        # 8. Verify resolve_selected_data_sources resolves successfully from in-memory cache
        from app.gateway.services_v1.data_source_service import resolve_selected_data_sources
        resolved = await resolve_selected_data_sources(request, "conv-starfish", ["mysql-1", "file-2"])
        assert len(resolved) == 2

        db_source = next(s for s in resolved if s["datasource_id"] == "mysql-1")
        assert db_source["type"] == "sql"
        assert db_source["metadata"]["host"] == "127.0.0.1"
        assert db_source["metadata"]["tables"] == ["data_source"]

        file_source = next(s for s in resolved if s["datasource_id"] == "file-2")
        assert file_source["type"] == "file"
        assert file_source["metadata"]["path"] == "/tmp/test.pdf"
    finally:
        reset_current_user(token)


@pytest.mark.asyncio
async def test_starfish_errors_and_timeout():
    from fastapi import HTTPException
    import httpx
    app = _make_app()
    scope = {"type": "http", "app": app, "headers": [], "method": "POST", "path": "/"}
    request = Request(scope)

    # 1. Mock 500 error from Starfish
    class MockResponse:
        def __init__(self, json_data, status_code):
            self._json_data = json_data
            self.status_code = status_code

        def json(self):
            return self._json_data

    mock_500 = AsyncMock(return_value=MockResponse({}, 500))
    with patch("httpx.AsyncClient.get", mock_500):
        with pytest.raises(HTTPException) as exc_info:
            await starfish_service.fetch_and_sync_data_sources("conv-starfish", request)
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["code"] == "DATA_SOURCE_UNAVAILABLE"

    # 2. Mock Timeout from Starfish
    mock_timeout = AsyncMock(side_effect=httpx.TimeoutException("Connection timed out"))
    with patch("httpx.AsyncClient.get", mock_timeout):
        with pytest.raises(HTTPException) as exc_info:
            await starfish_service.fetch_and_sync_data_sources("conv-starfish", request)
        assert exc_info.value.status_code == 504
        assert exc_info.value.detail["code"] == "DATA_SOURCE_TIMEOUT"


@pytest.mark.asyncio
async def test_starfish_partial_availability():
    app = _make_app()
    from app.gateway.services_v1.external_context import ExternalPrincipal
    from deerflow.runtime.user_context import reset_current_user, set_current_user
    from fastapi import HTTPException

    # Create conversation
    token = set_current_user(ExternalPrincipal(id="user-1"))
    try:
        await app.state.thread_store.create("conv-starfish-partial", metadata={})
    finally:
        reset_current_user(token)

    mock_starfish_response = {
        "msg": "操作成功",
        "code": 200,
        "data": [
            {
                "sourceId": "mysql-ok",
                "sourceType": "DATABASE",
                "sourceName": "MySQL OK",
                "sourceConfig": {
                    "databaseType": "MYSQL",
                    "password": "pass",
                    "databaseName": "db",
                    "port": 3306,
                    "host": "127.0.0.1",
                    "username": "root"
                }
            },
            {
                "sourceId": "mysql-fail",
                "sourceType": "DATABASE",
                "sourceName": "MySQL Fail",
                "sourceConfig": {
                    "databaseType": "MYSQL",
                    "password": "pass",
                    "databaseName": "db",
                    "port": 3306,
                    "host": "192.168.1.99",
                    "username": "root"
                }
            }
        ]
    }

    scope = {"type": "http", "app": app, "headers": [], "method": "POST", "path": "/"}
    request = Request(scope)

    class MockResponse:
        def __init__(self, json_data, status_code):
            self._json_data = json_data
            self.status_code = status_code

        def json(self):
            return self._json_data

    mock_get = AsyncMock(return_value=MockResponse(mock_starfish_response, 200))

    if "conv-starfish-partial" in _data_sources:
        del _data_sources["conv-starfish-partial"]

    # Mock connect: succeed for mysql-ok, fail for mysql-fail
    def mock_conn_side_effect(**kwargs):
        if kwargs.get("host") == "127.0.0.1":
            return MagicMock()
        raise Exception("Connection timeout")

    mock_connect = MagicMock(side_effect=mock_conn_side_effect)

    with patch("httpx.AsyncClient.get", mock_get), \
         patch("pymysql.connect", mock_connect):
        token = set_current_user(ExternalPrincipal(id="user-1"))
        try:
            await starfish_service.fetch_and_sync_data_sources("conv-starfish-partial", request)
        finally:
            reset_current_user(token)

    # Verify only mysql-ok is synchronized in memory
    assert "conv-starfish-partial" in _data_sources
    records = _data_sources["conv-starfish-partial"]
    assert len(records) == 1
    assert records[0].datasource_id == "mysql-ok"

    # Now verify if ALL are unavailable, it raises 503
    mock_connect_fail_all = MagicMock(side_effect=Exception("All connections fail"))
    if "conv-starfish-partial" in _data_sources:
        del _data_sources["conv-starfish-partial"]

    with patch("httpx.AsyncClient.get", mock_get), \
         patch("pymysql.connect", mock_connect_fail_all):
        token = set_current_user(ExternalPrincipal(id="user-1"))
        try:
            with pytest.raises(HTTPException) as exc_info:
                await starfish_service.fetch_and_sync_data_sources("conv-starfish-partial", request)
            assert exc_info.value.status_code == 503
            assert exc_info.value.detail["code"] == "DATA_SOURCE_UNAVAILABLE"
        finally:
            reset_current_user(token)


@pytest.mark.asyncio
async def test_query_data_source_tool():
    from deerflow.tools.builtins import query_data_source_tool
    from unittest.mock import AsyncMock, patch, MagicMock
    from langchain.tools import ToolRuntime
    from deerflow.agents.thread_state import ThreadState

    # Define mock data source in context
    selected_data_sources = [
        {
            "datasource_id": "mysql-test",
            "type": "sql",
            "name": "CustomsData",
            "metadata": {
                "db_type": "mysql",
                "host": "localhost",
                "port": 3306,
                "database": "customs",
                "username": "root",
                "password": "pwd"
            }
        }
    ]

    runtime = ToolRuntime(
        context={"selected_data_sources": selected_data_sources},
        config={},
        state=ThreadState(),
        stream_writer=MagicMock(),
        tools=[],
        tool_call_id="test_call",
        store=MagicMock()
    )

    # Mock nl_query_engine.query_sql
    mock_nl_res = {
        "generated_query": "SELECT * FROM transactions",
        "columns": ["id", "amount", "category"],
        "rows": [
            [1, 1000.0, "Electronics"],
            [2, 2500.0, "Machinery"]
        ],
        "row_count": 2
    }

    mock_query_sql = AsyncMock(return_value=mock_nl_res)

    with patch("app.gateway.services_v1.nl_query_engine.nl_query_engine.query_sql", mock_query_sql):
        res = await query_data_source_tool.ainvoke({"runtime": runtime, "query": "query customs data"})

    assert "Successfully queried database 'CustomsData'" in res
    assert "SELECT * FROM transactions" in res
    assert "Electronics" in res
    mock_query_sql.assert_called_once_with("query customs data", selected_data_sources[0]["metadata"])


@pytest.mark.asyncio
async def test_starfish_file_url_rewrite_and_download():
    app = _make_app()
    from app.gateway.services_v1.external_context import ExternalPrincipal
    from deerflow.runtime.user_context import reset_current_user, set_current_user
    
    # 1. Test url rewriting directly
    # MinIO console URL
    url_a = "http://172.16.0.160:19001/browser/datanet/法定代表人授权委托书.docx"
    # Direct download URL
    url_b = "http://172.16.0.160:25019/dip/common/file/download?path=datanet%2F6-1%E6%95%B0%E6%8D%AE%E6%9D%A5%E6%BA%90%E5%A3%B0%E6%98%8E_1782438779369.docx"
    
    rewritten_a = starfish_service._rewrite_url(url_a)
    rewritten_b = starfish_service._rewrite_url(url_b)
    
    # Expected rewritten URL A should point to port 25019 and use /dip/common/file/download?path=...
    assert "25019" in rewritten_a
    assert "/dip/common/file/download" in rewritten_a
    assert "path=datanet%2F%E6%B3%95%E5%AE%9A%E4%BB%A3%E8%A1%A8%E4%BA%BA%E6%8E%88%E6%9D%83%E5%A7%94%E6%89%98%E4%B9%A6.docx" in rewritten_a
    
    # URL B is already direct, should remain unchanged
    assert rewritten_b == url_b

    # 2. Test sync data sources with url
    mock_data = [
        {
            "sourceId": "file-url-rewrite",
            "sourceName": "Test URL Rewrite",
            "sourceType": "FILE",
            "sourceConfig": {
                "url": url_a,
                # "fileName" is intentionally omitted to test extraction
            }
        }
    ]

    scope = {"type": "http", "app": app, "headers": [], "method": "POST", "path": "/"}
    request = Request(scope)

    # Mock HTTP response for downloading the file content
    class MockDownloadResponse:
        def __init__(self, content, headers, status_code):
            self.content = content
            self.headers = headers
            self.status_code = status_code
        def json(self):
            return {}

    mock_client = AsyncMock()
    mock_get = AsyncMock(return_value=MockDownloadResponse(
        content=b"dummy docx bytes", 
        headers={"Content-Type": "application/octet-stream"}, 
        status_code=200
    ))
    mock_client.get = mock_get

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return mock_client
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    # Mock convert_file_to_markdown
    from pathlib import Path
    mock_md_path = MagicMock()
    mock_md_path.exists.return_value = True
    mock_md_path.read_text.return_value = "Parsed document content"
    mock_convert = AsyncMock(return_value=mock_md_path)

    # Clear in-memory cache
    if "conv-url-test" in _data_sources:
        del _data_sources["conv-url-test"]

    with patch("httpx.AsyncClient", MockAsyncClient), \
         patch("deerflow.utils.file_conversion.convert_file_to_markdown", mock_convert), \
         patch("pathlib.Path.write_bytes") as mock_write_bytes:
        
        token = set_current_user(ExternalPrincipal(id="user-1"))
        try:
            await app.state.thread_store.create("conv-url-test", metadata={})
            await starfish_service.sync_data_sources("conv-url-test", request, mock_data)
        finally:
            reset_current_user(token)

    # Verify download call was made with rewritten URL
    mock_get.assert_called_once_with(rewritten_a)

    # Verify content was updated from mock markdown output
    assert "conv-url-test" in _data_sources
    records = _data_sources["conv-url-test"]
    assert len(records) == 1
    assert records[0].content == "Parsed document content"
    assert records[0].name == "Test URL Rewrite"


