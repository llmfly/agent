from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse

from app.gateway.deps import get_config, get_run_manager
from app.gateway.internal_auth import create_internal_auth_headers
from app.gateway.routers.artifacts import get_artifact as get_thread_artifact
from app.gateway.routers.suggestions import SuggestionsRequest, SuggestionsResponse
from app.gateway.routers.suggestions import generate_suggestions as generate_thread_suggestions
from app.gateway.routers.thread_runs import RunCreateRequest, list_run_messages, stream_existing_run, thread_token_usage
from app.gateway.routers.thread_runs import cancel_run as cancel_thread_run
from app.gateway.routers.thread_runs import create_run as create_thread_run
from app.gateway.routers.thread_runs import get_run as get_thread_run
from app.gateway.routers.thread_runs import join_run as join_thread_run
from app.gateway.routers.thread_runs import list_run_events as list_thread_run_events
from app.gateway.routers.thread_runs import stream_run as stream_thread_run
from app.gateway.routers.thread_runs import wait_run as wait_thread_run
from app.gateway.routers.threads import ThreadHistoryRequest, ThreadStateResponse, ThreadStateUpdateRequest, get_thread_history, get_thread_state, update_thread_state
from app.gateway.routers.uploads import UploadLimits, UploadResponse, delete_uploaded_file, get_upload_limits, list_uploaded_files, upload_files
from app.gateway.schemas.v1.common import ArtifactDTO
from app.gateway.schemas.v1.conversations import (
    ConversationCreateRequest,
    ConversationDTO,
    ConversationListResponse,
    ConversationMessageRequest,
    ConversationMessageResponse,
    ConversationMessagesResponse,
    ConversationRunsResponse,
    ConversationSearchRequest,
    ConversationUpdateRequest,
)
from app.gateway.services import format_sse, iter_run_stream_entries, start_run
from app.gateway.services_v1.conversation_artifacts import merge_conversation_artifact_items
from app.gateway.services_v1.conversation_service import (
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversation_runs,
    list_conversations,
    list_messages,
    send_message,
    sync_artifacts_from_checkpoint,
    update_conversation,
)
from app.gateway.services_v1.data_source_service import (
    resolve_selected_data_sources,
    resolve_workspace_data_sources,
)
from app.gateway.services_v1.external_context import ExternalContext, get_external_context
from app.gateway.services_v1.run_adapter import build_run_create_request
from deerflow.config.app_config import AppConfig
from deerflow.runtime import END_SENTINEL, HEARTBEAT_SENTINEL

router = APIRouter(prefix="/conversations", tags=["v1-conversations"])
logger = logging.getLogger(__name__)
_DEFAULT_STREAM_TIMEOUT_SECONDS = 300.0
_DEFAULT_INTERNAL_GATEWAY_BASE_URL = "http://127.0.0.1:8005"
_RUN_ID_FROM_CONTENT_LOCATION = re.compile(r"/runs/([^/?#]+)")


def _unwrap_route(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func


def _use_thread_stream_proxy() -> bool:
    return os.getenv("V1_CONVERSATION_STREAM_USE_THREAD_PROXY", "0").lower() not in {"0", "false", "no"}


def _internal_gateway_base_url() -> str:
    return (os.getenv("GATEWAY_INTERNAL_BASE_URL") or os.getenv("DEER_FLOW_INTERNAL_GATEWAY_BASE_URL", _DEFAULT_INTERNAL_GATEWAY_BASE_URL)).rstrip("/")


def _forward_auth_headers(request: Request) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "text/event-stream", "Content-Type": "application/json"}
    for key in ("authorization", "x-app-id", "x-api-key", "x-user-id", "x-request-id"):
        value = request.headers.get(key)
        if value:
            headers[key] = value
    csrf_token = "v1-internal-thread-proxy"
    headers.update(create_internal_auth_headers())
    headers["X-CSRF-Token"] = csrf_token
    headers["Cookie"] = f"csrf_token={csrf_token}"
    return headers


def _decode_sse_data(lines: list[str]) -> object | None:
    if not lines:
        return None
    raw = "\n".join(lines)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _extract_run_id_from_content_location(value: str | None) -> str | None:
    if not value:
        return None
    match = _RUN_ID_FROM_CONTENT_LOCATION.search(value)
    return match.group(1) if match else None


@router.get("", response_model=ConversationListResponse, summary="List conversations", description="List external conversations for the caller.")
async def list_conversations_endpoint(
    request: Request,
    context: ExternalContext = Depends(get_external_context),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
):
    metadata = {"app_id": context.app_id}
    if context.external_user_id:
        metadata["external_user_id"] = context.external_user_id
    return await list_conversations(request, limit=limit, offset=offset, status=status, metadata=metadata)


@router.post("", response_model=ConversationDTO, summary="Create conversation", description="Create a new external conversation.")
async def create_conversation_endpoint(body: ConversationCreateRequest, request: Request, context: ExternalContext = Depends(get_external_context)):
    return await create_conversation(request, body, context)


@router.post("/search", response_model=ConversationListResponse, summary="Search conversations", description="Search conversations with metadata filters.")
async def search_conversations_endpoint(body: ConversationSearchRequest, request: Request, context: ExternalContext = Depends(get_external_context)):
    metadata = {"app_id": context.app_id, **(body.metadata or {})}
    if context.external_user_id:
        metadata["external_user_id"] = context.external_user_id
    return await list_conversations(request, limit=body.limit, offset=body.offset, status=body.status, metadata=metadata)


@router.get("/{conversation_id}", response_model=ConversationDTO, summary="Get conversation", description="Get conversation metadata without internal checkpoint fields.")
async def get_conversation_endpoint(conversation_id: str, request: Request, context: ExternalContext = Depends(get_external_context)):
    return await get_conversation(request, conversation_id)


@router.patch("/{conversation_id}", response_model=ConversationDTO, summary="Update conversation", description="Update conversation title or metadata.")
async def update_conversation_endpoint(conversation_id: str, body: ConversationUpdateRequest, request: Request, context: ExternalContext = Depends(get_external_context)):
    return await update_conversation(request, conversation_id, body)


@router.delete("/{conversation_id}", status_code=204, summary="Delete conversation", description="Delete a conversation and its internal thread metadata.")
async def delete_conversation_endpoint(conversation_id: str, request: Request, context: ExternalContext = Depends(get_external_context)):
    await delete_conversation(request, conversation_id)
    return Response(status_code=204)


@router.get("/{conversation_id}/messages", response_model=ConversationMessagesResponse, summary="List conversation messages", description="Return normalized chat messages for a conversation.")
async def list_messages_endpoint(
    conversation_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
    limit: int = Query(default=50, ge=1, le=200),
    before_seq: int | None = Query(default=None),
    after_seq: int | None = Query(default=None),
):
    return await list_messages(request, conversation_id, limit=limit, before_seq=before_seq, after_seq=after_seq)


@router.post("/{conversation_id}/messages", response_model=ConversationMessageResponse, summary="Send message", description="Send a non-streaming message to a conversation.")
async def send_message_endpoint(conversation_id: str, body: ConversationMessageRequest, request: Request, context: ExternalContext = Depends(get_external_context)):
    return await send_message(request, conversation_id, body, context)


@router.post("/{conversation_id}/stream", summary="Stream message", description="Send a message and stream normalized v1 SSE events.")
async def stream_message_endpoint(conversation_id: str, body: ConversationMessageRequest, request: Request, context: ExternalContext = Depends(get_external_context)):
    selected_data_sources = await resolve_selected_data_sources(request, conversation_id, body.datasource_ids, max_context_tokens=body.options.max_context_tokens)
    # Also resolve workspace-attached data sources and merge
    workspace_sources = await resolve_workspace_data_sources(conversation_id)
    if workspace_sources:
        existing_ids = {ds.get("datasource_id") for ds in selected_data_sources}
        for ws in workspace_sources:
            if ws.get("datasource_id") not in existing_ids:
                selected_data_sources.append(ws)
                existing_ids.add(ws.get("datasource_id"))
        logger.info(
            "stream_message: merged %d workspace data sources for conversation %s (total=%d)",
            len(workspace_sources), conversation_id, len(selected_data_sources),
        )

    run_body = build_run_create_request(body, context, selected_data_sources=selected_data_sources)
    timeout_seconds = float(os.getenv("V1_CONVERSATION_STREAM_TIMEOUT_SECONDS", str(_DEFAULT_STREAM_TIMEOUT_SECONDS)))

    async def _proxy_events():
        url = f"{_internal_gateway_base_url()}/api/threads/{conversation_id}/runs/stream"
        headers = _forward_auth_headers(request)
        run_id: str | None = None
        timeout = httpx.Timeout(connect=10.0, read=timeout_seconds, write=10.0, pool=10.0)

        async def cancel_upstream_run() -> None:
            if not run_id:
                return
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        f"{_internal_gateway_base_url()}/api/threads/{conversation_id}/runs/{run_id}/cancel",
                        params={"wait": 0, "action": "interrupt"},
                        headers=headers,
                    )
            except Exception as e:
                logger.warning("Failed to cancel proxied v1 stream run: conversation_id=%s run_id=%s error=%s", conversation_id, run_id, e)

        try:
            async with asyncio.timeout(timeout_seconds):
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream("POST", url, headers=headers, json=run_body.model_dump(mode="json", exclude_none=True)) as response:
                        if response.status_code >= 400:
                            detail = await response.aread()
                            yield format_sse(
                                "run.failed",
                                {
                                    "conversation_id": conversation_id,
                                    "error": {
                                        "code": "RUN_FAILED",
                                        "message": detail.decode("utf-8", "replace") or f"Thread stream returned HTTP {response.status_code}",
                                    },
                                },
                            )
                            return

                        run_id = _extract_run_id_from_content_location(response.headers.get("Content-Location"))
                        if run_id:
                            mapped = map_stream_event("metadata", {"run_id": run_id}, conversation_id=conversation_id, agent_id=body.agent_id)
                            if mapped is not None:
                                yield format_sse(mapped[0], mapped[1], event_id=None)

                        event_name: str | None = None
                        event_id: str | None = None
                        data_lines: list[str] = []
                        async for line in response.aiter_lines():
                            if line == "":
                                if event_name is None and not data_lines:
                                    continue
                                data = _decode_sse_data(data_lines)
                                if event_name == "metadata" and isinstance(data, dict):
                                    incoming_run_id = data.get("run_id")
                                    if isinstance(incoming_run_id, str):
                                        if run_id == incoming_run_id:
                                            event_name = None
                                            event_id = None
                                            data_lines = []
                                            continue
                                        run_id = incoming_run_id
                                if event_name == "end":
                                    try:
                                        await sync_artifacts_from_checkpoint(request, conversation_id, run_id or "")
                                    except Exception as e:
                                        logger.warning("Failed to sync artifacts during proxied stream: %s", e)
                                mapped = map_stream_event(event_name or "", data, conversation_id=conversation_id, agent_id=body.agent_id)
                                if mapped is not None:
                                    yield format_sse(mapped[0], mapped[1], event_id=event_id)
                                if event_name == "end":
                                    return
                                event_name = None
                                event_id = None
                                data_lines = []
                                continue
                            if line.startswith(":"):
                                yield f"{line}\n\n"
                                continue
                            if line.startswith("event:"):
                                event_name = line[6:].strip()
                                continue
                            if line.startswith("data:"):
                                data_lines.append(line[5:].lstrip())
                                continue
                            if line.startswith("id:"):
                                event_id = line[3:].strip()
                                continue
        except (TimeoutError, httpx.TimeoutException):
            logger.warning("v1 proxied conversation stream timed out: conversation_id=%s run_id=%s", conversation_id, run_id)
            await cancel_upstream_run()
            yield format_sse(
                "run.failed",
                {
                    "conversation_id": conversation_id,
                    "error": {
                        "code": "RUN_TIMEOUT",
                        "message": f"Run timed out after {timeout_seconds:g} seconds",
                    },
                },
            )
        except Exception as e:
            logger.warning("v1 proxied conversation stream failed: conversation_id=%s run_id=%s error=%s", conversation_id, run_id, e)
            await cancel_upstream_run()
            yield format_sse(
                "run.failed",
                {
                    "conversation_id": conversation_id,
                    "error": {
                        "code": "RUN_FAILED",
                        "message": str(e) or "Run failed",
                    },
                },
            )

    if _use_thread_stream_proxy():
        return StreamingResponse(
            _proxy_events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    record = await start_run(run_body, conversation_id, request)

    async def _events():
        run_manager = get_run_manager(request)
        stream = iter_run_stream_entries(request.app.state.stream_bridge, record, request, run_manager)
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            try:
                entry = await asyncio.wait_for(anext(stream), timeout=remaining)
            except StopAsyncIteration:
                return
            except TimeoutError:
                break

            if entry is END_SENTINEL:
                try:
                    await sync_artifacts_from_checkpoint(request, conversation_id, record.run_id)
                except Exception as e:
                    logger.warning("Failed to sync artifacts during stream: %s", e)
                mapped = map_stream_event("end", None, conversation_id=conversation_id, agent_id=body.agent_id)
                if mapped is not None:
                    yield format_sse(mapped[0], mapped[1], event_id=None)
                return

            if entry is HEARTBEAT_SENTINEL:
                yield ": heartbeat\n\n"
                continue

            mapped = map_stream_event(getattr(entry, "event", None), getattr(entry, "data", None), conversation_id=conversation_id, agent_id=body.agent_id)
            if mapped is None:
                continue
            yield format_sse(mapped[0], mapped[1], event_id=getattr(entry, "id", None))

        try:
            await stream.aclose()
        except Exception:
            logger.debug("Failed to close timed-out v1 stream iterator", exc_info=True)
        if record.status.name in {"pending", "running"}:
            logger.warning("v1 conversation stream timed out: conversation_id=%s run_id=%s", conversation_id, record.run_id)
            await run_manager.cancel(record.run_id)
        yield format_sse(
            "run.failed",
            {
                "conversation_id": conversation_id,
                "error": {
                    "code": "RUN_TIMEOUT",
                    "message": f"Run timed out after {timeout_seconds:g} seconds",
                },
            },
        )

    return StreamingResponse(
        _events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{conversation_id}/runs", response_model=ConversationRunsResponse, summary="List conversation runs", description="List runs for a conversation.")
async def list_conversation_runs_endpoint(conversation_id: str, request: Request, context: ExternalContext = Depends(get_external_context)):
    return await list_conversation_runs(request, conversation_id)


@router.post("/{conversation_id}/runs", summary="Create raw conversation run", description="Proxy to POST /api/threads/{thread_id}/runs.")
async def create_conversation_run_endpoint(
    conversation_id: str,
    body: RunCreateRequest,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
):
    return await _unwrap_route(create_thread_run)(thread_id=conversation_id, body=body, request=request)


@router.post("/{conversation_id}/runs/wait", summary="Create raw conversation run and wait", description="Proxy to POST /api/threads/{thread_id}/runs/wait.")
async def wait_conversation_run_endpoint(
    conversation_id: str,
    body: RunCreateRequest,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
):
    return await _unwrap_route(wait_thread_run)(thread_id=conversation_id, body=body, request=request)


@router.post("/{conversation_id}/runs/stream", summary="Create raw conversation run stream", description="Proxy to POST /api/threads/{thread_id}/runs/stream.")
async def stream_conversation_run_endpoint(
    conversation_id: str,
    body: RunCreateRequest,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
):
    return await _unwrap_route(stream_thread_run)(thread_id=conversation_id, body=body, request=request)


@router.get("/{conversation_id}/runs/{run_id}", summary="Get raw conversation run", description="Proxy to GET /api/threads/{thread_id}/runs/{run_id}.")
async def get_conversation_run_endpoint(
    conversation_id: str,
    run_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
):
    return await _unwrap_route(get_thread_run)(thread_id=conversation_id, run_id=run_id, request=request)


@router.post("/{conversation_id}/runs/{run_id}/cancel", summary="Cancel raw conversation run", description="Proxy to POST /api/threads/{thread_id}/runs/{run_id}/cancel.")
async def cancel_conversation_run_endpoint(
    conversation_id: str,
    run_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
    wait: bool = Query(default=False),
    action: Literal["interrupt", "rollback"] = Query(default="interrupt"),
):
    return await _unwrap_route(cancel_thread_run)(thread_id=conversation_id, run_id=run_id, request=request, wait=wait, action=action)


@router.get("/{conversation_id}/runs/{run_id}/join", summary="Join raw conversation run stream", description="Proxy to GET /api/threads/{thread_id}/runs/{run_id}/join.")
async def join_conversation_run_endpoint(
    conversation_id: str,
    run_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
):
    return await _unwrap_route(join_thread_run)(thread_id=conversation_id, run_id=run_id, request=request)


async def _stream_existing_conversation_run(
    conversation_id: str,
    run_id: str,
    request: Request,
    action: Literal["interrupt", "rollback"] | None,
    wait: int,
):
    return await _unwrap_route(stream_existing_run)(thread_id=conversation_id, run_id=run_id, request=request, action=action, wait=wait)


@router.get("/{conversation_id}/runs/{run_id}/stream", summary="Stream existing raw conversation run", description="Proxy to GET /api/threads/{thread_id}/runs/{run_id}/stream.")
async def stream_existing_conversation_run_endpoint(
    conversation_id: str,
    run_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
    action: Literal["interrupt", "rollback"] | None = Query(default=None),
    wait: int = Query(default=0),
):
    return await _stream_existing_conversation_run(conversation_id=conversation_id, run_id=run_id, request=request, action=action, wait=wait)


@router.post("/{conversation_id}/runs/{run_id}/stream", summary="Stream or cancel existing raw conversation run", description="Proxy to POST /api/threads/{thread_id}/runs/{run_id}/stream.")
async def post_stream_existing_conversation_run_endpoint(
    conversation_id: str,
    run_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
    action: Literal["interrupt", "rollback"] | None = Query(default=None),
    wait: int = Query(default=0),
):
    return await _stream_existing_conversation_run(conversation_id=conversation_id, run_id=run_id, request=request, action=action, wait=wait)


@router.get("/{conversation_id}/runs/{run_id}/events", summary="List raw conversation run events", description="Proxy to GET /api/threads/{thread_id}/runs/{run_id}/events.")
async def list_conversation_run_events_endpoint(
    conversation_id: str,
    run_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
    event_types: str | None = Query(default=None),
    limit: int = Query(default=500, le=2000),
):
    return await _unwrap_route(list_thread_run_events)(thread_id=conversation_id, run_id=run_id, request=request, event_types=event_types, limit=limit)


@router.get("/{conversation_id}/artifacts", response_model=list[ArtifactDTO], summary="List conversation artifacts", description="List all artifacts generated in a conversation.")
async def list_conversation_artifacts_endpoint(
    conversation_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
) -> list[ArtifactDTO]:
    from app.gateway.services_v1.artifact_service import artifact_service
    arts = await artifact_service.list_conversation_artifacts(conversation_id)

    items: list[ArtifactDTO] = []
    seen_paths: set[str] = set()
    for art in arts:
        if art.files:
            for f in art.files:
                if f.file_path:
                    path_key = f.file_path
                    if path_key not in seen_paths:
                        seen_paths.add(path_key)
                        # DB artifacts use /api/v1/artifacts/{id} as URL.
                        # The by-path endpoint only works for sandbox virtual paths
                        # (e.g. mnt/user-data/outputs/...), not host absolute paths.
                        base_url = f.download_url or f"/api/v1/artifacts/{f.file_id}"
                        items.append(
                            ArtifactDTO(
                                artifact_id=f"path:{path_key}",
                                conversation_id=conversation_id,
                                run_id=art.run_id,
                                filename=f.filename,
                                mime_type=None,
                                url=base_url,
                                created_at=f.created_at.isoformat() if f.created_at else None,
                                metadata={
                                    "source": "artifact_service",
                                    "path": path_key,
                                    "download_url": f"{base_url}?download=true",
                                },
                            )
                        )
        else:
            # Fallback for artifacts without files on disk
            items.append(
                ArtifactDTO(
                    artifact_id=art.artifact_id,
                    conversation_id=conversation_id,
                    run_id=art.run_id,
                    filename=None,
                    mime_type=None,
                    url=f"/api/v1/artifacts/{art.artifact_id}",
                    created_at=art.created_at.isoformat() if art.created_at else None,
                    metadata={
                        "name": art.name,
                        "status": art.status,
                        "meta": art.meta_json,
                    },
                )
            )

    # Also load legacy path-based artifacts from thread state
    state_artifacts: list[object] = []
    try:
        state = await _unwrap_route(get_thread_state)(thread_id=conversation_id, request=request)
        values = getattr(state, "values", {}) or {}
        if isinstance(values, dict):
            raw_artifacts = values.get("artifacts") or []
            if isinstance(raw_artifacts, list):
                state_artifacts = raw_artifacts
    except Exception as e:
        logger.warning("Failed to load thread state artifacts for conversation %s: %s", conversation_id, e)

    return merge_conversation_artifact_items(
        conversation_id=conversation_id,
        persisted_items=items,
        state_artifacts=state_artifacts,
        dto_factory=ArtifactDTO,
    )


@router.get("/{conversation_id}/artifacts/by-path/{path:path}", summary="Get conversation artifact file by virtual path")
async def get_conversation_artifact_by_path_endpoint(
    conversation_id: str,
    path: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
    download: bool = Query(default=False),
):
    return await _unwrap_route(get_thread_artifact)(thread_id=conversation_id, path=path, request=request, download=download)


@router.post("/{conversation_id}/uploads", response_model=UploadResponse, summary="Upload files to a conversation")
async def upload_conversation_files_endpoint(
    conversation_id: str,
    request: Request,
    files: list[UploadFile] = File(...),
    context: ExternalContext = Depends(get_external_context),
    config: AppConfig = Depends(get_config),
) -> UploadResponse:
    return await _unwrap_route(upload_files)(thread_id=conversation_id, request=request, files=files, config=config)


@router.get("/{conversation_id}/uploads", response_model=dict, summary="List conversation uploads")
async def list_conversation_uploads_endpoint(
    conversation_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
) -> dict:
    return await _unwrap_route(list_uploaded_files)(thread_id=conversation_id, request=request)


@router.get("/{conversation_id}/uploads/limits", response_model=UploadLimits, summary="Get conversation upload limits")
async def get_conversation_upload_limits_endpoint(
    conversation_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
    config: AppConfig = Depends(get_config),
) -> UploadLimits:
    return await _unwrap_route(get_upload_limits)(thread_id=conversation_id, request=request, config=config)


@router.delete("/{conversation_id}/uploads/{filename}", summary="Delete a conversation upload")
async def delete_conversation_upload_endpoint(
    conversation_id: str,
    filename: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
) -> dict:
    return await _unwrap_route(delete_uploaded_file)(thread_id=conversation_id, filename=filename, request=request)


@router.get("/{conversation_id}/state", response_model=ThreadStateResponse, summary="Get conversation state")
async def get_conversation_state_endpoint(conversation_id: str, request: Request, context: ExternalContext = Depends(get_external_context)) -> ThreadStateResponse:
    state = await _unwrap_route(get_thread_state)(thread_id=conversation_id, request=request)

    # Merge all artifact sources into the top-level state.artifacts field:

    # 1. Checkpoint artifacts (from present_files tool, sandbox virtual paths)
    checkpoint_artifacts: list[str] = []
    values = getattr(state, "values", {}) or {}
    if isinstance(values, dict):
        raw = values.get("artifacts") or []
        if isinstance(raw, list):
            checkpoint_artifacts = [a for a in raw if isinstance(a, str)]

    # 2. DB-persisted artifacts (from report workflow, host absolute paths)
    try:
        from app.gateway.services_v1.artifact_service import artifact_service
        arts = await artifact_service.list_conversation_artifacts(conversation_id)
        db_paths: list[str] = []
        seen: set[str] = set()
        for art in arts:
            if art.files:
                for f in art.files:
                    if f.file_path and f.file_path not in seen:
                        seen.add(f.file_path)
                        db_paths.append(f.file_path)
    except Exception as e:
        logger.warning("Failed to enrich state with artifacts: %s", e)
        db_paths = []

    # Merge: checkpoint first (preserves order), then DB paths not already included
    merged = list(checkpoint_artifacts)
    seen_in_merged = set(merged)
    for p in db_paths:
        if p not in seen_in_merged:
            merged.append(p)
            seen_in_merged.add(p)

    state.artifacts = merged
    return state


@router.patch("/{conversation_id}/state", response_model=ThreadStateResponse, summary="Update conversation state")
async def update_conversation_state_endpoint(
    conversation_id: str,
    body: ThreadStateUpdateRequest,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
) -> ThreadStateResponse:
    return await _unwrap_route(update_thread_state)(thread_id=conversation_id, body=body, request=request)


@router.get("/{conversation_id}/history", summary="Get conversation checkpoint history")
async def get_conversation_history_endpoint(
    conversation_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
    limit: int = Query(default=10, ge=1, le=100),
    before: str | None = Query(default=None),
):
    return await _unwrap_route(get_thread_history)(thread_id=conversation_id, body=ThreadHistoryRequest(limit=limit, before=before), request=request)


@router.get("/{conversation_id}/runs/{run_id}/messages", summary="List messages for a conversation run")
async def list_conversation_run_messages_endpoint(
    conversation_id: str,
    run_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
    limit: int = Query(default=50, le=200, ge=1),
    before_seq: int | None = Query(default=None),
    after_seq: int | None = Query(default=None),
) -> dict:
    return await _unwrap_route(list_run_messages)(
        thread_id=conversation_id,
        run_id=run_id,
        request=request,
        limit=limit,
        before_seq=before_seq,
        after_seq=after_seq,
    )


@router.get("/{conversation_id}/token-usage", summary="Get conversation token usage")
async def get_conversation_token_usage_endpoint(
    conversation_id: str,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
    include_active: bool = Query(default=False),
):
    return await _unwrap_route(thread_token_usage)(thread_id=conversation_id, request=request, include_active=include_active)


@router.post("/{conversation_id}/suggestions", response_model=SuggestionsResponse, summary="Generate conversation follow-up suggestions")
async def generate_conversation_suggestions_endpoint(
    conversation_id: str,
    body: SuggestionsRequest,
    request: Request,
    context: ExternalContext = Depends(get_external_context),
    config: AppConfig = Depends(get_config),
) -> SuggestionsResponse:
    return await _unwrap_route(generate_thread_suggestions)(thread_id=conversation_id, body=body, request=request, config=config)
