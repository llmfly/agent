"""DataSource DTOs for v1 external API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


DataSourceType = Literal["text", "file", "url", "sql", "es"]


class DataSourceCreateRequest(BaseModel):
    """Request to register a data source.

    For type=sql, metadata should include:
      - db_type, host, port, database, username, password
      (schema auto-discovered on query)
    For type=es, metadata should include:
      - hosts, index, username, password (optional)
    """

    type: DataSourceType = Field(description="Data source type: text, file, url, sql, es")
    name: str = Field(description="Display name for the data source")
    content: str | None = Field(default=None, description="Content for text type data source")
    url: str | None = Field(default=None, description="URL for url type data source")
    file_id: str | None = Field(default=None, description="Upload file ID for file type data source")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Connection params for sql/es types")


class DataSourceResponse(BaseModel):
    """Response model for a data source."""

    datasource_id: str = Field(description="Unique data source identifier")
    conversation_id: str = Field(description="Parent conversation ID")
    type: DataSourceType = Field(description="Data source type")
    name: str = Field(description="Display name")
    content_preview: str = Field(default="", description="Preview of the content (first 200 chars)")
    status: str = Field(default="ready", description="Status: ready, processing, error")
    created_at: str = Field(default="", description="ISO timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataSourceListResponse(BaseModel):
    """List of data sources for a conversation."""

    datasources: list[DataSourceResponse]
    total: int = 0


class DataSourceQueryRequest(BaseModel):
    """Request to query a data source with natural language."""

    query: str = Field(description="Natural language query to execute against the data source")
    max_results: int = Field(default=50, ge=1, le=1000, description="Maximum results to return")


class DataSourceQueryResponse(BaseModel):
    """Response containing query results from a data source."""

    datasource_id: str
    query: str
    generated_query: str = Field(description="The generated SQL/ES query")
    columns: list[str] = Field(default_factory=list, description="Column names")
    rows: list[list[Any]] = Field(default_factory=list, description="Query result rows")
    row_count: int = 0
    error: str | None = None
