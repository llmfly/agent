"""Workspace Data Source Management API — user-owned data assets.

Implements the design from ``docs/design/data-source-management.md``.

Key concepts:
- DataSource: user-owned data asset (database, file, object storage, API)
- ConversationDataSource: reference (attach) from conversation to data source
- Three-layer: User → DataSource → ConversationDataSource
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Path, Request, UploadFile

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
    DataSourceUploadResponse,
    UpdateAttachRequest,
)
from app.gateway.services_v1.workspace_datasource_service import workspace_datasource_service
from deerflow.runtime.user_context import reset_current_user, set_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspace", tags=["v1-workspace"])


async def _require_user(request: Request) -> AsyncIterator[str]:
    """Resolve the authenticated user from the JWT cookie.

    The ``/api/v1/`` prefix is public in ``AuthMiddleware``, so the
    middleware does **not** stamp the user contextvar for these paths.
    This dependency fills that gap by reading the ``access_token`` cookie
    and setting ``deerflow.runtime.user_context``, matching the pattern
    used by ``get_external_context`` for header-based auth.
    """
    from app.gateway.deps import get_current_user_from_request

    user = await get_current_user_from_request(request)
    token = set_current_user(user)
    try:
        yield str(user.id)
    finally:
        reset_current_user(token)


# ── DataSource File Upload ────────────────────────────────────────────────

_DATA_SOURCE_UPLOAD_DIR = Path("/data/intelli/engine/.deer-flow/data/datasource-files")


@router.post("/data-sources/upload", response_model=DataSourceUploadResponse)
async def upload_datasource_file(
    file: UploadFile = File(...),
    user_id: str = Depends(_require_user),
) -> DataSourceUploadResponse:
    """Upload a file for a file-type data source (pdf, docx, etc.)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Determine file extension
    ext = os.path.splitext(file.filename)[1].lower()
    # Guard: only allow known file types
    ALLOWED_EXTS = {".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".csv", ".pptx", ".ppt", ".md"}
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Create user-level upload directory
    user_upload_dir = _DATA_SOURCE_UPLOAD_DIR / user_id
    user_upload_dir.mkdir(parents=True, exist_ok=True)

    # Save file with unique name to avoid collisions
    safe_name = f"{uuid.uuid4().hex[:12]}_{file.filename}"
    file_path = user_upload_dir / safe_name

    content = await file.read()
    file_size = len(content)
    if file_size > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    file_path.write_bytes(content)

    config = {
        "file_path": str(file_path),
        "filename": file.filename,
        "file_size": file_size,
    }

    logger.info("File uploaded for datasource: %s (%d bytes) by user %s", safe_name, file_size, user_id)

    return DataSourceUploadResponse(
        filename=file.filename,
        file_path=str(file_path),
        file_size=file_size,
        config=config,
    )


# ── DataSource CRUD ─────────────────────────────────────────────────────────


@router.post("/data-sources", response_model=DataSourceResponse, status_code=201)
async def create_datasource(
    body: DataSourceCreateRequest,
    user_id: str = Depends(_require_user),
) -> DataSourceResponse:
    """Create a new data source for the current user."""
    return await workspace_datasource_service.create_datasource(user_id, body)


@router.get("/data-sources", response_model=DataSourceListResponse)
async def list_datasources(
    type: str | None = None,
    search: str | None = None,
    user_id: str = Depends(_require_user),
) -> DataSourceListResponse:
    """List data sources for the current user."""
    return await workspace_datasource_service.list_datasources(
        user_id, type_filter=type, search=search,
    )


@router.get("/data-sources/{datasource_id}", response_model=DataSourceResponse)
async def get_datasource(
    datasource_id: str = Path(description="Data source ID"),
    user_id: str = Depends(_require_user),
) -> DataSourceResponse:
    """Get a single data source."""
    result = await workspace_datasource_service.get_datasource(user_id, datasource_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Data source not found")
    return result


@router.put("/data-sources/{datasource_id}", response_model=DataSourceResponse)
async def update_datasource(
    datasource_id: str = Path(description="Data source ID"),
    body: DataSourceUpdateRequest = None,  # type: ignore
    user_id: str = Depends(_require_user),
) -> DataSourceResponse:
    """Update a data source."""
    result = await workspace_datasource_service.update_datasource(user_id, datasource_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="Data source not found")
    return result


@router.delete("/data-sources/{datasource_id}", status_code=204)
async def delete_datasource(
    datasource_id: str = Path(description="Data source ID"),
    user_id: str = Depends(_require_user),
) -> None:
    """Delete a data source (soft delete)."""
    deleted = await workspace_datasource_service.delete_datasource(user_id, datasource_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Data source not found")


@router.post("/data-sources/test", response_model=DataSourceTestResponse)
async def test_datasource_connection(
    body: DataSourceTestRequest,
    user_id: str = Depends(_require_user),
) -> DataSourceTestResponse:
    """Test a data source connection before saving."""
    return await workspace_datasource_service.test_connection(body)


# ── Conversation Attachment Management ──────────────────────────────────────


@router.post(
    "/conversations/{conversation_id}/datasources",
    response_model=AttachedDataSourceResponse,
    status_code=201,
)
async def attach_datasource(
    conversation_id: str = Path(description="Conversation ID"),
    body: AttachDataSourceRequest = None,  # type: ignore
    user_id: str = Depends(_require_user),
) -> AttachedDataSourceResponse:
    """Attach a data source to a conversation."""
    try:
        result = await workspace_datasource_service.attach_datasource(
            user_id, conversation_id, body,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Data source not found or access denied")
        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "Unhandled error in attach_datasource(user=%s, conv=%s, ds=%s)",
            user_id, conversation_id, body.datasource_id if body else "N/A",
        )
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/conversations/{conversation_id}/datasources",
    response_model=AttachedDataSourceListResponse,
)
async def list_attached_datasources(
    conversation_id: str = Path(description="Conversation ID"),
) -> AttachedDataSourceListResponse:
    """List all data sources attached to a conversation."""
    return await workspace_datasource_service.list_attached_datasources(conversation_id)


@router.delete(
    "/conversations/{conversation_id}/datasources/{datasource_id}",
    status_code=204,
)
async def detach_datasource(
    conversation_id: str = Path(description="Conversation ID"),
    datasource_id: str = Path(description="Data source ID"),
) -> None:
    """Detach a data source from a conversation."""
    deleted = await workspace_datasource_service.detach_datasource(conversation_id, datasource_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Attached datasource not found")


@router.put(
    "/conversations/{conversation_id}/datasources/{datasource_id}",
    response_model=AttachedDataSourceResponse,
)
async def update_attached_datasource(
    conversation_id: str = Path(description="Conversation ID"),
    datasource_id: str = Path(description="Data source ID"),
    body: UpdateAttachRequest = None,  # type: ignore
) -> AttachedDataSourceResponse:
    """Update the alias or mount_path of an attached data source."""
    result = await workspace_datasource_service.update_attach(
        conversation_id, datasource_id, body,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Attached datasource not found")
    return result
