"""Workspace Data Source Management service — user-owned data assets.

Implements the design from ``docs/design/data-source-management.md``:

- DataSource: user-owned data asset (DB, file, object store, API)
- ConversationDataSource: reference from conversation to data source
- Three-layer architecture: User → DataSource → ConversationDataSource
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.gateway.schemas.v1.datasource_workspace import (
    AttachDataSourceRequest,
    AttachedDataSourceListResponse,
    AttachedDataSourceResponse,
    DataSourceCreateRequest,
    DataSourceListResponse,
    DataSourceResponse,
    DataSourceTestRequest,
    DataSourceTestResponse,
    DataSourceUpdateRequest,
    UpdateAttachRequest,
)
from deerflow.persistence.datasource.model import ConversationDataSourceRow, DataSourceRow
from deerflow.persistence.engine import get_session_factory

logger = logging.getLogger(__name__)


def _ensure_config_dict(raw: Any) -> dict[str, Any]:
    """Normalize config_json to dict regardless of storage backend.

    SQLite stores config_json as a JSON string (String variant), while
    Postgres stores it as native JSONB (returned as dict). This helper
    handles both cases transparently.
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _ds_row_to_response(
    row: DataSourceRow,
    conversation_count: int = 0,
) -> DataSourceResponse:
    return DataSourceResponse(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        description=row.description or "",
        type=row.type,
        status=row.status,
        icon=row.icon or "",
        config=_ensure_config_dict(row.config_json),
        created_at=row.created_at,
        updated_at=row.updated_at,
        conversation_count=conversation_count,
    )


def _attach_row_to_response(
    row: ConversationDataSourceRow,
) -> AttachedDataSourceResponse:
    ds = row.datasource if hasattr(row, "datasource") and row.datasource else None
    return AttachedDataSourceResponse(
        id=row.id,
        conversation_id=row.conversation_id,
        datasource_id=row.datasource_id,
        alias=row.alias,
        mount_path=row.mount_path,
        created_at=row.created_at,
        name=ds.name if ds else "",
        type=ds.type if ds else "",
        status=ds.status if ds else "",
        icon=ds.icon if ds else "",
    )


def _get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    """Get the async session factory."""
    try:
        return get_session_factory()
    except Exception:
        return None


def _is_sqlite() -> bool:
    """Check if the current database backend is SQLite.

    SQLite stores the JSONB-variant ``config_json`` column as a plain
    ``String``, so dict values must be serialized before insert.
    """
    try:
        from deerflow.config.app_config import get_app_config

        return get_app_config().database.backend == "sqlite"
    except Exception:
        return False


class WorkspaceDataSourceService:
    """User-owned data asset management with conversation references."""

    async def create_datasource(
        self,
        user_id: str,
        request: DataSourceCreateRequest,
    ) -> DataSourceResponse:
        """Create a new data source for a user."""
        sf = _get_session_factory()
        if sf is None:
            raise RuntimeError("Session factory not available")

        ds_id = f"ds_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)

        # SQLite stores config_json as String (not native JSONB), so
        # we need to serialize the dict to a JSON string. Postgres JSONB
        # accepts dict natively.
        raw_config = request.config or {}
        config_value: dict | str = raw_config
        if _is_sqlite():
            config_value = json.dumps(raw_config, ensure_ascii=False)

        row = DataSourceRow(
            id=ds_id,
            user_id=user_id,
            name=request.name.strip(),
            description=request.description.strip() if request.description else "",
            type=request.type,
            status="ready",
            config_json=config_value,
            created_at=now,
            updated_at=now,
        )

        async with sf() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
            logger.info("DataSource created: %s (type=%s, user=%s)", ds_id, request.type, user_id)
            return _ds_row_to_response(row)

    async def list_datasources(
        self,
        user_id: str,
        *,
        type_filter: str | None = None,
        search: str | None = None,
        include_deleted: bool = False,
    ) -> DataSourceListResponse:
        """List data sources for a user, with optional filters."""
        sf = _get_session_factory()
        if sf is None:
            return DataSourceListResponse(datasources=[], total=0)

        async with sf() as session:
            stmt = select(DataSourceRow).where(DataSourceRow.user_id == user_id)
            if not include_deleted:
                stmt = stmt.where(DataSourceRow.deleted == False)  # noqa: E712
            if type_filter:
                stmt = stmt.where(DataSourceRow.type == type_filter)
            if search:
                stmt = stmt.where(DataSourceRow.name.ilike(f"%{search}%"))

            stmt = stmt.order_by(DataSourceRow.updated_at.desc())
            result = await session.execute(stmt)
            rows = result.scalars().all()

            # Count conversations per datasource
            ds_ids = [r.id for r in rows]
            conv_counts: dict[str, int] = {}
            if ds_ids:
                from sqlalchemy import func

                count_stmt = (
                    select(
                        ConversationDataSourceRow.datasource_id,
                        func.count(ConversationDataSourceRow.id),
                    )
                    .where(ConversationDataSourceRow.datasource_id.in_(ds_ids))
                    .group_by(ConversationDataSourceRow.datasource_id)
                )
                count_result = await session.execute(count_stmt)
                for ds_id, cnt in count_result:
                    conv_counts[ds_id] = cnt

            items = [_ds_row_to_response(r, conv_counts.get(r.id, 0)) for r in rows]
            return DataSourceListResponse(datasources=items, total=len(items))

    async def get_datasource(self, user_id: str, datasource_id: str) -> DataSourceResponse | None:
        """Get a single data source by ID."""
        sf = _get_session_factory()
        if sf is None:
            return None

        async with sf() as session:
            row = await session.get(DataSourceRow, datasource_id)
            if row is None or row.deleted or row.user_id != user_id:
                return None

            # Count conversations referencing this datasource
            from sqlalchemy import func

            count_stmt = (
                select(func.count(ConversationDataSourceRow.id))
                .where(ConversationDataSourceRow.datasource_id == datasource_id)
            )
            count_result = await session.execute(count_stmt)
            conv_count = count_result.scalar() or 0

            return _ds_row_to_response(row, conv_count)

    async def update_datasource(
        self,
        user_id: str,
        datasource_id: str,
        request: DataSourceUpdateRequest,
    ) -> DataSourceResponse | None:
        """Update data source metadata/config."""
        sf = _get_session_factory()
        if sf is None:
            return None

        async with sf() as session:
            row = await session.get(DataSourceRow, datasource_id)
            if row is None or row.deleted or row.user_id != user_id:
                return None

            update_fields = {}
            if request.name is not None:
                update_fields["name"] = request.name.strip()
            if request.description is not None:
                update_fields["description"] = request.description.strip()
            if request.type is not None:
                update_fields["type"] = request.type
            if request.status is not None:
                update_fields["status"] = request.status
            if request.icon is not None:
                update_fields["icon"] = request.icon
            if request.config is not None:
                update_fields["config_json"] = request.config
            update_fields["updated_at"] = datetime.now(UTC)

            if update_fields:
                await session.execute(
                    sa_update(DataSourceRow)
                    .where(DataSourceRow.id == datasource_id)
                    .values(**update_fields)
                )
                await session.commit()
                await session.refresh(row)

            logger.info("DataSource updated: %s", datasource_id)
            return _ds_row_to_response(row)

    async def delete_datasource(self, user_id: str, datasource_id: str, *, hard: bool = False) -> bool:
        """Delete (soft or hard) a data source."""
        sf = _get_session_factory()
        if sf is None:
            return False

        async with sf() as session:
            row = await session.get(DataSourceRow, datasource_id)
            if row is None or row.user_id != user_id:
                return False

            if hard:
                await session.delete(row)
            else:
                row.deleted = True
                row.updated_at = datetime.now(UTC)

            await session.commit()
            logger.info("DataSource deleted: %s (hard=%s)", datasource_id, hard)
            return True

    async def test_connection(self, request: DataSourceTestRequest) -> DataSourceTestResponse:
        """Test a data source connection."""
        ds_type = request.type
        config = request.config or {}

        try:
            if ds_type == "mysql":
                return await self._test_mysql(config)
            elif ds_type == "postgresql":
                return await self._test_postgresql(config)
            elif ds_type == "es":
                return await self._test_es(config)
            else:
                return DataSourceTestResponse(
                    success=True,
                    message=f"Connection test not implemented for type '{ds_type}', saved as-is",
                )
        except Exception as e:
            return DataSourceTestResponse(
                success=False,
                message=f"Connection failed: {e!s}",
            )

    async def _test_mysql(self, config: dict) -> DataSourceTestResponse:
        import pymysql

        conn = pymysql.connect(
            host=config.get("host", "localhost"),
            port=int(config.get("port", 3306)),
            user=config.get("username", ""),
            password=config.get("password", ""),
            database=config.get("database", ""),
            connect_timeout=5,
        )
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT VERSION() AS v")
                version = cur.fetchone()[0]
        return DataSourceTestResponse(
            success=True,
            message=f"Connected successfully. MySQL version: {version}",
            details={"version": version},
        )

    async def _test_postgresql(self, config: dict) -> DataSourceTestResponse:
        import asyncpg  # type: ignore

        conn = await asyncpg.connect(
            host=config.get("host", "localhost"),
            port=int(config.get("port", 5432)),
            user=config.get("username", ""),
            password=config.get("password", ""),
            database=config.get("database", ""),
            timeout=5,
        )
        version = await conn.fetchval("SELECT VERSION()")
        await conn.close()
        return DataSourceTestResponse(
            success=True,
            message=f"Connected successfully. PostgreSQL version: {version}",
            details={"version": version},
        )

    async def _test_es(self, config: dict) -> DataSourceTestResponse:
        import httpx

        hosts = config.get("hosts", ["http://localhost:9200"])
        url = hosts[0] if isinstance(hosts, list) else hosts
        auth = None
        if config.get("username"):
            auth = (config["username"], config.get("password", ""))

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url, auth=auth)
            resp.raise_for_status()
            info = resp.json()

        return DataSourceTestResponse(
            success=True,
            message=f"Connected to Elasticsearch {info.get('version', {}).get('number', 'unknown')}",
            details={"cluster": info.get("cluster_name", ""), "version": info.get("version", {})},
        )

    # ── Conversation Attachment Management ─────────────────────────────

    async def attach_datasource(
        self,
        user_id: str,
        conversation_id: str,
        request: AttachDataSourceRequest,
    ) -> AttachedDataSourceResponse | None:
        """Attach (reference) a data source to a conversation."""
        sf = _get_session_factory()
        if sf is None:
            return None

        async with sf() as session:
            # Verify datasource exists and belongs to user
            ds = await session.get(DataSourceRow, request.datasource_id)
            if ds is None or ds.deleted or ds.user_id != user_id:
                return None

            # Check if already attached
            existing = await session.execute(
                select(ConversationDataSourceRow).where(
                    ConversationDataSourceRow.conversation_id == conversation_id,
                    ConversationDataSourceRow.datasource_id == request.datasource_id,
                )
            )
            if existing.scalar_one_or_none():
                logger.info(
                    "DataSource already attached: %s -> %s",
                    conversation_id, request.datasource_id,
                )
                return await self.get_attached_datasource(
                    conversation_id, request.datasource_id,
                )

            ref_id = f"cds_{uuid.uuid4().hex[:12]}"
            ref = ConversationDataSourceRow(
                id=ref_id,
                conversation_id=conversation_id,
                datasource_id=request.datasource_id,
                alias=request.alias,
            )
            session.add(ref)
            await session.commit()
            await session.refresh(ref)

            logger.info(
                "DataSource attached: %s -> %s (alias=%s)",
                conversation_id, request.datasource_id, request.alias,
            )
            return _attach_row_to_response(ref)

    async def detach_datasource(
        self,
        conversation_id: str,
        datasource_id: str,
    ) -> bool:
        """Detach (remove reference) a data source from a conversation."""
        sf = _get_session_factory()
        if sf is None:
            return False

        async with sf() as session:
            result = await session.execute(
                select(ConversationDataSourceRow).where(
                    ConversationDataSourceRow.conversation_id == conversation_id,
                    ConversationDataSourceRow.datasource_id == datasource_id,
                )
            )
            ref = result.scalar_one_or_none()
            if ref is None:
                return False

            await session.delete(ref)
            await session.commit()

            logger.info("DataSource detached: %s <- %s", conversation_id, datasource_id)
            return True

    async def update_attach(
        self,
        conversation_id: str,
        datasource_id: str,
        request: UpdateAttachRequest,
    ) -> AttachedDataSourceResponse | None:
        """Update the alias/mount_path of an attached data source."""
        sf = _get_session_factory()
        if sf is None:
            return None

        async with sf() as session:
            result = await session.execute(
                select(ConversationDataSourceRow).where(
                    ConversationDataSourceRow.conversation_id == conversation_id,
                    ConversationDataSourceRow.datasource_id == datasource_id,
                )
            )
            ref = result.scalar_one_or_none()
            if ref is None:
                return None

            if request.alias is not None:
                ref.alias = request.alias

            await session.commit()
            await session.refresh(ref)
            return _attach_row_to_response(ref)

    async def get_attached_datasource(
        self,
        conversation_id: str,
        datasource_id: str,
    ) -> AttachedDataSourceResponse | None:
        """Get a single attached datasource reference."""
        sf = _get_session_factory()
        if sf is None:
            return None

        async with sf() as session:
            result = await session.execute(
                select(ConversationDataSourceRow).where(
                    ConversationDataSourceRow.conversation_id == conversation_id,
                    ConversationDataSourceRow.datasource_id == datasource_id,
                )
            )
            ref = result.scalar_one_or_none()
            if ref is None:
                return None
            return _attach_row_to_response(ref)

    async def list_attached_datasources(
        self,
        conversation_id: str,
    ) -> AttachedDataSourceListResponse:
        """List all data sources attached to a conversation."""
        sf = _get_session_factory()
        if sf is None:
            return AttachedDataSourceListResponse(datasources=[], total=0)

        async with sf() as session:
            result = await session.execute(
                select(ConversationDataSourceRow)
                .where(ConversationDataSourceRow.conversation_id == conversation_id)
                .order_by(ConversationDataSourceRow.created_at.asc())
            )
            refs = result.scalars().all()
            items = [_attach_row_to_response(r) for r in refs]
            return AttachedDataSourceListResponse(datasources=items, total=len(items))

    async def get_data_sources_for_conversation(
        self,
        conversation_id: str,
    ) -> list[dict[str, Any]]:
        """Get all data sources attached to a conversation (for tool injection).

        Returns the format expected by ``query_data_source_tool``
        and ``_format_data_sources_for_prompt``.
        """
        sf = _get_session_factory()
        if sf is None:
            return []

        async with sf() as session:
            result = await session.execute(
                select(ConversationDataSourceRow)
                .where(ConversationDataSourceRow.conversation_id == conversation_id)
            )
            refs = result.scalars().all()

            ds_list = []
            for ref in refs:
                ds = ref.datasource
                if ds is None or ds.deleted:
                    continue

                alias = ref.alias or ds.name
                config = _ensure_config_dict(ds.config_json)

                item: dict[str, Any] = {
                    "datasource_id": ds.id,
                    "type": ds.type,
                    "name": alias,
                    "content": "",
                    "metadata": config,
                }

                if ds.type in ("sql", "mysql", "postgresql"):
                    item["content"] = (
                        f"[SQL] {config.get('db_type', ds.type)}://"
                        f"{config.get('host', 'localhost')}/{config.get('database', '')}"
                    )
                elif ds.type == "es":
                    hosts = config.get("hosts", ["http://localhost:9200"])
                    item["content"] = f"[ES] {hosts}"
                elif ds.type in ("pdf", "docx", "txt", "xlsx", "csv"):
                    item["content"] = f"[File] {config.get('object_key', '')}"

                ds_list.append(item)

            return ds_list


# Singleton
workspace_datasource_service = WorkspaceDataSourceService()
