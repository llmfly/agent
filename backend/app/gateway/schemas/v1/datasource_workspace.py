"""Pydantic schemas for the Workspace Data Source Management API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── DataSource ────────────────────────────────────────────────────────────


class DataSourceCreateRequest(BaseModel):
    """Create a new data source (user-owned data asset)."""

    name: str = Field(..., min_length=1, max_length=128, description="Data source name")
    description: str | None = Field(None, description="Description")
    type: str = Field(..., description="Type: mysql/postgresql/clickhouse/es/minio/s3/pdf/docx/txt/xlsx/csv/ppt")
    config: dict[str, Any] | None = Field(None, description="Connection config as JSON dict")


class DataSourceUpdateRequest(BaseModel):
    """Update data source metadata or config."""

    name: str | None = Field(None, max_length=128)
    description: str | None = None
    type: str | None = None
    config: dict[str, Any] | None = None
    status: str | None = None
    icon: str | None = None


class DataSourceResponse(BaseModel):
    """Data source response."""

    id: str
    user_id: str
    name: str
    description: str = ""
    type: str
    status: str
    icon: str = ""
    config: dict[str, Any] = {}
    created_at: datetime | None = None
    updated_at: datetime | None = None
    conversation_count: int = 0


class DataSourceListResponse(BaseModel):
    """Paginated data source list."""

    datasources: list[DataSourceResponse]
    total: int


class DataSourceTestRequest(BaseModel):
    """Test connection request."""

    type: str
    config: dict[str, Any]


class DataSourceTestResponse(BaseModel):
    """Test connection result."""

    success: bool
    message: str = ""
    details: dict[str, Any] = {}


class DataSourceUploadResponse(BaseModel):
    """File upload result for file-type data sources."""

    filename: str
    file_path: str
    file_size: int
    config: dict[str, Any]


# ── ConversationDataSource (Attach/Detach) ────────────────────────────────


class AttachDataSourceRequest(BaseModel):
    """Attach (reference) a data source to a conversation."""

    datasource_id: str
    alias: str | None = Field(None, description="Friendly alias shown to Agent")


class UpdateAttachRequest(BaseModel):
    """Update a conversation-data-source reference."""

    alias: str | None = None


class AttachedDataSourceResponse(BaseModel):
    """A data source attached to a conversation."""

    id: str
    conversation_id: str
    datasource_id: str
    alias: str | None = None
    mount_path: str | None = None
    created_at: datetime | None = None

    # Joined datasource info
    name: str = ""
    type: str = ""
    status: str = ""
    icon: str = ""


class AttachedDataSourceListResponse(BaseModel):
    """List of attached data sources."""

    datasources: list[AttachedDataSourceResponse]
    total: int
