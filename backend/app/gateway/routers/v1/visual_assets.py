from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from app.gateway.schemas.v1.visual_assets import (
    VisualAssetCancelRequest,
    VisualAssetCancelResponse,
    VisualAssetCreateResponse,
    VisualAssetGenerateRequest,
    VisualAssetJobDTO,
    VisualAssetSimpleCreateResponse,
    VisualAssetSimpleGenerateRequest,
    VisualAssetSimpleJobDTO,
)
from app.gateway.services_v1.external_context import ExternalContext, get_external_context
from app.gateway.services_v1.visual_asset_service import visual_asset_service

router = APIRouter(prefix="/ai/visual-assets", tags=["v1-visual-assets"])


@router.post(
    "/generate",
    response_model=VisualAssetCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate visual assets",
    description="Create an asynchronous visual asset generation job for logos, notebook icons, notebook backgrounds, cover images, or general images.",
)
async def generate_visual_assets(
    body: VisualAssetGenerateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    context: ExternalContext = Depends(get_external_context),
) -> VisualAssetCreateResponse:
    response = visual_asset_service.create_job(request, body, context)
    background_tasks.add_task(visual_asset_service.process_job, request, response.job_id, context)
    return response


@router.post(
    "/simple/generate",
    response_model=VisualAssetSimpleCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate visual assets with a simplified request",
    description="Create an asynchronous visual asset generation job with a flat request and compact response for frontend clients.",
)
async def generate_visual_assets_simple(
    body: VisualAssetSimpleGenerateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    context: ExternalContext = Depends(get_external_context),
) -> VisualAssetSimpleCreateResponse:
    response = visual_asset_service.create_simple_job(request, body, context)
    background_tasks.add_task(visual_asset_service.process_job, request, response.job_id, context)
    return response


@router.get(
    "/jobs/{job_id}",
    response_model=VisualAssetJobDTO,
    summary="Get visual asset job",
    description="Get visual asset generation progress and generated artifact references.",
)
async def get_visual_asset_job(
    job_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
) -> VisualAssetJobDTO:
    return visual_asset_service.get_job(request, job_id, context)


@router.get(
    "/simple/jobs/{job_id}",
    response_model=VisualAssetSimpleJobDTO,
    summary="Get visual asset job with a simplified response",
    description="Get compact visual asset generation progress and generated preview/download URLs.",
)
async def get_visual_asset_job_simple(
    job_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
) -> VisualAssetSimpleJobDTO:
    return visual_asset_service.get_simple_job(request, job_id, context)


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=VisualAssetCancelResponse,
    summary="Cancel visual asset job",
    description="Cancel a queued or running visual asset generation job.",
)
async def cancel_visual_asset_job(
    job_id: str,
    body: VisualAssetCancelRequest,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
) -> VisualAssetCancelResponse:
    return visual_asset_service.cancel_job(request, job_id, context, reason=body.reason)
