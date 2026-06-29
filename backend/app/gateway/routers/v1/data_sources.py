"""v1 DataSource API — register and query data sources for conversations."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from app.gateway.schemas.v1.data_sources import (
    DataSourceCreateRequest,
    DataSourceListResponse,
    DataSourceQueryRequest,
    DataSourceQueryResponse,
    DataSourceResponse,
)
from app.gateway.services_v1.data_source_service import DataSourceService
from app.gateway.services_v1.external_context import ExternalContext, get_external_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations/{conversation_id}/data-sources", tags=["v1-data-sources"])

data_source_service = DataSourceService()


@router.post("", response_model=DataSourceResponse, status_code=201)
async def create_datasource(
    conversation_id: str = Path(description="Conversation ID"),
    body: DataSourceCreateRequest = None,  # type: ignore
    request: Request = None,  # type: ignore
    context: ExternalContext = Depends(get_external_context),
) -> DataSourceResponse:
    """Register a data source. Types: text, file, url, sql, es."""
    return await data_source_service.create_datasource(conversation_id, body, req=request)


@router.get("", response_model=DataSourceListResponse)
async def list_datasources(
    conversation_id: str = Path(description="Conversation ID"),
    request: Request = None,  # type: ignore
    context: ExternalContext = Depends(get_external_context),
) -> DataSourceListResponse:
    items = await data_source_service.list_datasources(conversation_id)
    return DataSourceListResponse(datasources=items, total=len(items))


@router.get("/{datasource_id}", response_model=DataSourceResponse)
async def get_datasource(
    conversation_id: str = Path(description="Conversation ID"),
    datasource_id: str = Path(description="Data source ID"),
    request: Request = None,  # type: ignore
    context: ExternalContext = Depends(get_external_context),
) -> DataSourceResponse:
    result = await data_source_service.get_datasource(conversation_id, datasource_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"DataSource {datasource_id} not found")
    return result


@router.delete("/{datasource_id}", status_code=204)
async def delete_datasource(
    conversation_id: str = Path(description="Conversation ID"),
    datasource_id: str = Path(description="Data source ID"),
    request: Request = None,  # type: ignore
    context: ExternalContext = Depends(get_external_context),
) -> None:
    """Delete a data source."""
    deleted = await data_source_service.delete_datasource(conversation_id, datasource_id, req=request)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"DataSource {datasource_id} not found")


@router.post("/{datasource_id}/query", response_model=DataSourceQueryResponse)
async def query_datasource(
    conversation_id: str = Path(description="Conversation ID"),
    datasource_id: str = Path(description="Data source ID"),
    body: DataSourceQueryRequest = None,  # type: ignore
    request: Request = None,  # type: ignore
    context: ExternalContext = Depends(get_external_context),
) -> DataSourceQueryResponse:
    """Query a data source using natural language.

    SQL sources: Text-to-SQL pipeline (auto schema discovery → LLM → execute).
    ES sources: Text-to-ES (NL → ES DSL → execute).
    Text/file/url sources: returns stored content.
    """
    return await data_source_service.query_datasource(conversation_id, datasource_id, body)
