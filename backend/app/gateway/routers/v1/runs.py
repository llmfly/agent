from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.gateway.deps import get_feedback_repo
from app.gateway.routers.feedback import FeedbackResponse, FeedbackUpsertRequest
from app.gateway.routers.thread_runs import join_run as join_thread_run
from app.gateway.routers.thread_runs import stream_existing_run
from app.gateway.schemas.v1.common import RunDTO
from app.gateway.schemas.v1.runs import RunCancelRequest, RunCancelResponse
from app.gateway.services_v1.external_context import ExternalContext, get_external_context
from app.gateway.services_v1.run_service import cancel_run, get_run

router = APIRouter(prefix="/runs", tags=["v1-runs"])


def _unwrap_route(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func


@router.get("/{run_id}", response_model=RunDTO, summary="Get run", description="Get normalized run status and token usage.")
async def get_run_endpoint(run_id: str, request: Request, context: ExternalContext = Depends(get_external_context)):
    return await get_run(request, run_id)


@router.post("/{run_id}/cancel", response_model=RunCancelResponse, summary="Cancel run", description="Cancel a pending or running run.")
async def cancel_run_endpoint(run_id: str, body: RunCancelRequest, request: Request, context: ExternalContext = Depends(get_external_context)):
    ok = await cancel_run(request, run_id, action=body.action, wait=body.wait)
    if not ok:
        raise HTTPException(status_code=409, detail="Run is not cancellable")
    return RunCancelResponse(run_id=run_id, status="cancel_requested")


@router.get("/{run_id}/join", summary="Join run stream", description="Join an existing normalized run's SSE stream.")
async def join_run_endpoint(run_id: str, request: Request, context: ExternalContext = Depends(get_external_context)):
    run = await get_run(request, run_id)
    return await _unwrap_route(join_thread_run)(thread_id=run.conversation_id, run_id=run_id, request=request)


async def _stream_existing_v1_run(
    run_id: str,
    request: Request,
    action: Literal["interrupt", "rollback"] | None,
    wait: int,
):
    run = await get_run(request, run_id)
    return await _unwrap_route(stream_existing_run)(thread_id=run.conversation_id, run_id=run_id, request=request, action=action, wait=wait)


@router.get("/{run_id}/stream", response_model=None, summary="Stream existing run")
async def stream_run_endpoint(
    run_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
    action: Literal["interrupt", "rollback"] | None = Query(default=None),
    wait: int = Query(default=0),
):
    return await _stream_existing_v1_run(run_id=run_id, request=request, action=action, wait=wait)


@router.post("/{run_id}/stream", response_model=None, summary="Stream or cancel-then-stream existing run")
async def post_stream_run_endpoint(
    run_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
    action: Literal["interrupt", "rollback"] | None = Query(default=None),
    wait: int = Query(default=0),
):
    return await _stream_existing_v1_run(run_id=run_id, request=request, action=action, wait=wait)


@router.put("/{run_id}/feedback", response_model=FeedbackResponse, summary="Create or update run feedback")
async def upsert_run_feedback_endpoint(run_id: str, body: FeedbackUpsertRequest, request: Request, context: ExternalContext = Depends(get_external_context)):
    if body.rating not in (1, -1):
        raise HTTPException(status_code=400, detail="rating must be +1 or -1")
    run = await get_run(request, run_id)
    feedback_repo = get_feedback_repo(request)
    return await feedback_repo.upsert(
        run_id=run_id,
        thread_id=run.conversation_id,
        rating=body.rating,
        user_id=context.external_user_id,
        comment=body.comment,
    )


@router.delete("/{run_id}/feedback", summary="Delete current user's run feedback")
async def delete_run_feedback_endpoint(run_id: str, request: Request, context: ExternalContext = Depends(get_external_context)):
    run = await get_run(request, run_id)
    feedback_repo = get_feedback_repo(request)
    deleted = await feedback_repo.delete_by_run(
        thread_id=run.conversation_id,
        run_id=run_id,
        user_id=context.external_user_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="No feedback found for this run")
    return {"success": True}
