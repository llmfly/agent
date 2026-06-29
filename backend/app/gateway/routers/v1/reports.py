"""v1 Report API — generate and query reports from data sources and conversations."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from app.gateway.schemas.v1.reports import ReportCreateRequest, ReportResponse, ReportStatusResponse
from app.gateway.services_v1.data_source_service import DataSourceService
from app.gateway.services_v1.external_context import ExternalContext, get_external_context
from app.gateway.services_v1.report_service import ReportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations/{conversation_id}/reports", tags=["v1-reports"])
status_router = APIRouter(prefix="/reports", tags=["v1-reports"])

_report_service: ReportService | None = None


def _get_report_service() -> ReportService:
    global _report_service
    if _report_service is None:
        _report_service = ReportService(DataSourceService())
    return _report_service


@router.post("", response_model=ReportResponse, status_code=201)
async def create_report(
    conversation_id: str = Path(description="Conversation ID"),
    body: ReportCreateRequest = None,  # type: ignore
    request: Request = None,  # type: ignore
    context: ExternalContext = Depends(get_external_context),
) -> ReportResponse:
    """Generate a report based on data sources and conversation context."""
    svc = _get_report_service()
    user_id = context.external_user_id or context.app_id
    result = await svc.create_report(conversation_id, body, user_id=user_id)
    return ReportResponse(
        report_id=result.report_id,
        conversation_id=result.conversation_id,
        status=result.status,
        created_at=result.created_at,
    )


@status_router.get("/{report_id}", response_model=ReportStatusResponse)
async def get_report(
    report_id: str = Path(description="Report ID"),
    request: Request = None,  # type: ignore
    context: ExternalContext = Depends(get_external_context),
) -> ReportStatusResponse:
    """Get report generation status and download URLs."""
    svc = _get_report_service()
    result = await svc.get_report(report_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return result
