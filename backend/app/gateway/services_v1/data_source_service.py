"""DataSource service — register, query, and manage data sources for conversations.

Supports:
- text: Direct text content
- file: Uploaded file reference
- url: URL reference
- sql: SQL database connection (enterprise Text-to-SQL pipeline)
- es: Elasticsearch connection (Text-to-ES)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request

from app.gateway.schemas.v1.data_sources import (
    DataSourceCreateRequest,
    DataSourceQueryRequest,
    DataSourceQueryResponse,
    DataSourceResponse,
    DataSourceType,
)
from app.gateway.services_v1.nl_query_engine import NLQueryEngine

logger = logging.getLogger(__name__)


class DataSourceRecord:
    """Internal data source record."""

    def __init__(
        self,
        datasource_id: str,
        conversation_id: str,
        type: DataSourceType,
        name: str,
        content: str,
        status: str = "ready",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.datasource_id = datasource_id
        self.conversation_id = conversation_id
        self.type = type
        self.name = name
        self.content = content
        self.status = status
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc).isoformat()


# In-memory store: conversation_id -> list of DataSourceRecord
_data_sources: dict[str, list[DataSourceRecord]] = {}


class DataSourceService:
    """Service for managing data sources per conversation."""

    def __init__(self) -> None:
        self._nl_engine = NLQueryEngine()

    async def create_datasource(
        self,
        conversation_id: str,
        request: DataSourceCreateRequest,
        req: Request | None = None,  # optional, for thread_store persistence
    ) -> DataSourceResponse:
        datasource_id = f"ds_{uuid.uuid4().hex[:12]}"

        content = ""
        if request.type == "text":
            content = request.content or ""
        elif request.type == "url":
            content = f"[URL] {request.url or ''}"
        elif request.type == "file":
            content = f"[File] {request.file_id or ''}"
        elif request.type == "sql":
            meta = request.metadata or {}
            db_type = meta.get("db_type", "mysql")
            database = meta.get("database", "")
            host = meta.get("host", "localhost")
            content = f"[SQL] {db_type}://{host}/{database}"
        elif request.type == "es":
            meta = request.metadata or {}
            hosts = meta.get("hosts", ["http://localhost:9200"])
            index = meta.get("index", "")
            content = f"[ES] {hosts}/{index}"

        record = DataSourceRecord(
            datasource_id=datasource_id,
            conversation_id=conversation_id,
            type=request.type,
            name=request.name,
            content=content,
            metadata=request.metadata,
        )

        if conversation_id not in _data_sources:
            _data_sources[conversation_id] = []
        _data_sources[conversation_id].append(record)

        # Persist to thread_store so the data source survives restarts
        # and is accessible via both v1 API and internal thread API paths.
        if req is not None:
            try:
                from app.gateway.deps import get_thread_store
                thread_store = get_thread_store(req)

                # Get or create the thread record
                thread_record = await thread_store.get(conversation_id)
                if thread_record is None:
                    thread_record = await thread_store.create(
                        conversation_id,
                        metadata={_DATA_SOURCES_KEY: []},
                    )

                if thread_record is not None:
                    meta = dict(thread_record.get("metadata") or {})
                    persisted = list(meta.get(_DATA_SOURCES_KEY, []))
                    persisted.append({
                        "datasource_id": datasource_id,
                        "type": request.type,
                        "name": request.name,
                        "content": content,
                        "metadata": request.metadata,
                    })
                    meta[_DATA_SOURCES_KEY] = persisted
                    await thread_store.update_metadata(conversation_id, meta)
                    logger.info(
                        "DataSource persisted to thread_store: %s (conversation=%s)",
                        datasource_id, conversation_id,
                    )
            except Exception as e:
                logger.warning("Failed to persist data source to thread_store: %s", e)

        logger.info("DataSource created: %s (type=%s, name=%s)", datasource_id, request.type, request.name)
        return self._record_to_response(record)

    async def list_datasources(self, conversation_id: str) -> list[DataSourceResponse]:
        records = _data_sources.get(conversation_id, [])
        return [self._record_to_response(r) for r in records]

    async def get_datasource(self, conversation_id: str, datasource_id: str) -> DataSourceResponse | None:
        records = _data_sources.get(conversation_id, [])
        for r in records:
            if r.datasource_id == datasource_id:
                return self._record_to_response(r)
        return None

    async def get_datasource_content(self, conversation_id: str, datasource_id: str) -> str | None:
        records = _data_sources.get(conversation_id, [])
        for r in records:
            if r.datasource_id == datasource_id:
                return r.content
        return None

    async def delete_datasource(
        self,
        conversation_id: str,
        datasource_id: str,
        req: Request | None = None,
    ) -> bool:
        """Delete a data source from memory and thread_store."""
        # 1) Remove from in-memory cache
        records = _data_sources.get(conversation_id, [])
        found = False
        for i, r in enumerate(records):
            if r.datasource_id == datasource_id:
                records.pop(i)
                found = True
                break
        if not found:
            return False

        # 2) Remove from thread_store DB
        if req is not None:
            try:
                from app.gateway.deps import get_thread_store
                thread_store = get_thread_store(req)
                thread_record = await thread_store.get(conversation_id)
                if thread_record is not None:
                    meta = dict(thread_record.get("metadata") or {})
                    persisted: list = list(meta.get(_DATA_SOURCES_KEY, []))
                    persisted = [ds for ds in persisted if ds.get("datasource_id") != datasource_id]
                    meta[_DATA_SOURCES_KEY] = persisted
                    await thread_store.update_metadata(conversation_id, meta)
                    logger.info(
                        "DataSource deleted from thread_store: %s (conversation=%s)",
                        datasource_id, conversation_id,
                    )
            except Exception as e:
                logger.warning("Failed to delete data source from thread_store: %s", e)

        logger.info("DataSource deleted: %s (conversation=%s)", datasource_id, conversation_id)
        return True

    async def query_datasource(
        self,
        conversation_id: str,
        datasource_id: str,
        query_request: DataSourceQueryRequest,
    ) -> DataSourceQueryResponse:
        """Query a data source using natural language.

        For SQL data sources, runs the full enterprise pipeline:
        QueryRewriter → SchemaRetriever → EntityLinker → QueryPlanner
        → FewShotRetrieval → ContextBuilder → LLM → SQLGlotValidator
        → CostEstimator → Optimizer → Repairer(retry) → Executor

        For ES data sources: NL → ES DSL → execute.
        For text/file/url: returns stored content.
        """
        records = _data_sources.get(conversation_id, [])
        record = next((r for r in records if r.datasource_id == datasource_id), None)

        if record is None:
            return DataSourceQueryResponse(
                datasource_id=datasource_id, query=query_request.query,
                generated_query="", error=f"DataSource {datasource_id} not found",
            )

        if record.type == "sql":
            result = await self._nl_engine.query_sql(
                query_request.query, record.metadata, max_results=query_request.max_results,
            )
            return DataSourceQueryResponse(
                datasource_id=datasource_id, query=query_request.query,
                generated_query=result.get("generated_query", ""),
                columns=result.get("columns", []), rows=result.get("rows", []),
                row_count=result.get("row_count", 0), error=result.get("error"),
            )

        elif record.type == "es":
            result = await self._nl_engine.query_es(
                query_request.query, record.metadata, max_results=query_request.max_results,
            )
            return DataSourceQueryResponse(
                datasource_id=datasource_id, query=query_request.query,
                generated_query=result.get("generated_query", ""),
                columns=result.get("columns", []), rows=result.get("rows", []),
                row_count=result.get("row_count", 0), error=result.get("error"),
            )

        else:
            return DataSourceQueryResponse(
                datasource_id=datasource_id, query=query_request.query,
                generated_query="", columns=["content"], rows=[[record.content]],
                row_count=1 if record.content else 0,
            )

    async def get_all_content(
        self,
        conversation_id: str,
        datasource_ids: list[str] | None = None,
        user_query: str | None = None,
    ) -> str:
        """Get concatenated content from specified (or all) data sources.

        For SQL/ES data sources, performs NL-to-query and includes results.
        """
        records = _data_sources.get(conversation_id, [])
        if datasource_ids:
            records = [r for r in records if r.datasource_id in datasource_ids]

        parts = []
        for i, r in enumerate(records, 1):
            parts.append(f"[数据源 {i}: {r.name} ({r.type})]")
            if r.type in ("sql", "es"):
                try:
                    # When the caller didn't provide a specific user_query, use
                    # the data source name as a default so SQL/ES sources always
                    # return actual data instead of just a connection string.
                    query_text = user_query or f"查询{r.name}的全部数据"
                    qr = DataSourceQueryRequest(query=query_text, max_results=50)
                    qr_resp = await self.query_datasource(conversation_id, r.datasource_id, qr)
                    if qr_resp.error:
                        parts.append(f"  查询出错: {qr_resp.error}")
                    else:
                        parts.append(f"  生成查询: {qr_resp.generated_query}")
                        parts.append(f"  结果: {qr_resp.row_count} 条记录")
                        if qr_resp.columns and qr_resp.rows:
                            header = " | ".join(str(c) for c in qr_resp.columns)
                            parts.append(f"  {header}")
                            parts.append(f"  {'-' * len(header)}")
                            for row in qr_resp.rows[:20]:
                                parts.append("  " + " | ".join(str(c) for c in row))
                            if qr_resp.row_count > 20:
                                parts.append(f"  ... 还有 {qr_resp.row_count - 20} 条记录")
                except Exception as e:
                    parts.append(f"  查询异常: {e}")
            else:
                parts.append(r.content)
            parts.append("")
        return "\n".join(parts)

    @staticmethod
    def _record_to_response(record: DataSourceRecord) -> DataSourceResponse:
        return DataSourceResponse(
            datasource_id=record.datasource_id,
            conversation_id=record.conversation_id,
            type=record.type,
            name=record.name,
            content_preview=record.content[:200] if record.content else "",
            status=record.status,
            created_at=record.created_at,
            metadata=record.metadata,
        )


# ── resolve_selected_data_sources (v1 external API, uses thread_store) ──

_DATA_SOURCES_KEY = "_v1_data_sources"


async def resolve_selected_data_sources(
    request: Request, conversation_id: str, datasource_ids: list[str], *, max_context_tokens: int | None = None,
) -> list[dict[str, Any]]:
    """Resolve data source metadata by IDs from memory cache or thread store.

    When ``datasource_ids`` is empty, returns ALL available data sources
    for the conversation — so the agent can access every registered data
    source even when the caller doesn't explicitly select any.
    """

    # 1. Collect all available data sources for this conversation
    all_sources: dict[str, dict[str, Any]] = {}

    # a) From memory cache
    records = _data_sources.get(conversation_id, [])
    logger.info("resolve_selected_data_sources: %d records in memory cache for conversation %s", len(records), conversation_id)
    for r in records:
        logger.info("  memory record: id=%s type=%s name=%s", r.datasource_id, r.type, r.name)
        all_sources[r.datasource_id] = {
            "datasource_id": r.datasource_id,
            "type": r.type,
            "name": r.name,
            "content": r.content,
            "metadata": r.metadata,
        }

    # b) From thread store (persisted)
    from app.gateway.deps import get_thread_store
    thread_store = get_thread_store(request)
    record = await thread_store.get(conversation_id)
    if record is not None:
        persisted_meta = dict(record.get("metadata") or {})
        persisted_sources = persisted_meta.get(_DATA_SOURCES_KEY, [])
        logger.info("resolve_selected_data_sources: %d persisted sources in thread_store for conversation %s", len(persisted_sources), conversation_id)
        for item in persisted_sources:
            did = item.get("datasource_id")
            if did and did not in all_sources:
                logger.info("  persisted source: id=%s type=%s name=%s", did, item.get("type"), item.get("name"))
                all_sources[did] = item
    else:
        logger.info("resolve_selected_data_sources: no thread_store record for conversation %s", conversation_id)

    # 2. If caller specified IDs, filter — otherwise return all
    if datasource_ids:
        missing = [did for did in datasource_ids if did not in all_sources]
        if missing:
            raise HTTPException(status_code=404, detail={"code": "DATA_SOURCE_NOT_FOUND", "datasource_ids": missing})
        return [all_sources[did] for did in datasource_ids]

    # No IDs specified → return all available data sources
    logger.info("No datasource_ids specified — auto-including all %d data sources for conversation %s", len(all_sources), conversation_id)
    return list(all_sources.values())


# ── Direct access helpers (for tools that don't go through v1 layer) ──


def get_data_sources_for_conversation(conversation_id: str) -> list[dict[str, Any]]:
    """Read data sources from the per-process memory cache.

    Only finds records created on the **same** Gateway worker. For
    cross-worker access, use :func:`get_data_sources_for_conversation_db`.
    """
    records = _data_sources.get(conversation_id, [])
    if not records:
        return []
    result = []
    for r in records:
        result.append({
            "datasource_id": r.datasource_id,
            "type": r.type,
            "name": r.name,
            "content": r.content,
            "metadata": r.metadata,
        })
    return result


async def get_data_sources_for_conversation_db(conversation_id: str) -> list[dict[str, Any]]:
    """Read data sources from the thread_store DB (cross-worker safe).

    Gateway runs with multiple workers, each in its own process. The
    ``_data_sources`` dict is per-process, so this function queries the
    shared database directly.
    """
    try:
        from deerflow.persistence.engine import get_session_factory
        from deerflow.persistence.thread_meta.model import ThreadMetaRow

        sf = get_session_factory()
        if sf is None:
            return []

        async with sf() as session:
            row = await session.get(ThreadMetaRow, conversation_id)
            if row is None:
                return []
            meta = row.metadata_json or {}
            persisted = meta.get("_v1_data_sources", [])
            if persisted:
                logger.info(
                    "get_data_sources_for_conversation_db: %d records from DB for %s",
                    len(persisted), conversation_id,
                )
            return persisted
    except ImportError:
        return []
    except Exception as e:
        logger.warning("get_data_sources_for_conversation_db failed: %s", e)
        return []


async def resolve_workspace_data_sources(conversation_id: str) -> list[dict[str, Any]]:
    """Resolve workspace-attached data sources for a conversation.

    Queries the ``conversation_datasource`` + ``datasource`` tables and
    returns records in the format expected by ``selected_data_sources``
    for agent tool injection.

    This replaces the previous starfish_server integration — the agent
    now reads data sources that the user explicitly attached via the
    workspace DataSourcePanel.
    """
    try:
        from app.gateway.services_v1.workspace_datasource_service import (
            workspace_datasource_service,
        )

        return await workspace_datasource_service.get_data_sources_for_conversation(
            conversation_id,
        )
    except ImportError:
        logger.warning("workspace_datasource_service not available")
        return []
    except Exception as e:
        logger.warning("resolve_workspace_data_sources failed: %s", e)
        return []


# Singleton
data_source_service = DataSourceService()
