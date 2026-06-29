from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from fastapi import HTTPException, Request
from langgraph.checkpoint.base import empty_checkpoint

from app.gateway.deps import get_checkpointer, get_run_event_store, get_run_manager, get_thread_store
from app.gateway.schemas.v1.common import MessageDTO, PaginationDTO, RunDTO, UsageDTO
from app.gateway.schemas.v1.conversations import (
    ConversationCreateRequest,
    ConversationDTO,
    ConversationListResponse,
    ConversationMessageRequest,
    ConversationMessagesResponse,
    ConversationRunsResponse,
    ConversationUpdateRequest,
)
from app.gateway.services import start_run, wait_for_run_completion
from app.gateway.services_v1.data_source_service import (
    resolve_selected_data_sources,
    resolve_workspace_data_sources,
)
from app.gateway.services_v1.external_context import ExternalContext, build_external_metadata
from app.gateway.services_v1.run_adapter import build_run_create_request
from deerflow.config.paths import get_paths
from deerflow.utils.time import coerce_iso, now_iso

logger = logging.getLogger(__name__)

_FILE_DATA_SOURCE_TYPES = {"pdf", "docx", "txt", "xlsx", "csv"}


def _sync_workspace_files_to_uploads(
    data_sources: list[dict[str, Any]],
    conversation_id: str,
    user_id: str | None,
) -> None:
    """Copy workspace-attached file data sources into the sandbox uploads directory.

    The sandbox uploads dir (`/mnt/user-data/uploads/`) is where the LLM's
    environment expects files. Workspace data source files live elsewhere on
    the host filesystem. This function copies them so the ``UploadsMiddleware``
    picks them up and the LLM can find them.

    This is a best-effort operation: failures to resolve paths or copy files
    are logged but do not block message sending.
    """
    if not user_id or user_id == "anonymous":
        logger.debug("_sync_workspace_files_to_uploads: no valid user_id, skipping")
        return

    try:
        paths = get_paths()
        uploads_dir = paths.sandbox_uploads_dir(conversation_id, user_id=user_id)
        uploads_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.warning("_sync_workspace_files_to_uploads: failed to resolve uploads dir: %s", exc)
        return

    file_sources = [
        ds for ds in data_sources
        if ds.get("type") in _FILE_DATA_SOURCE_TYPES
    ]
    if not file_sources:
        return

    for ds in file_sources:
        meta = ds.get("metadata") or {}
        src_path_str = meta.get("file_path", "")
        if not src_path_str:
            continue

        src = Path(src_path_str)
        if not src.is_file():
            logger.warning(
                "_sync_workspace_files_to_uploads: source file not found: %s (ds=%s)",
                src_path_str, ds.get("datasource_id"),
            )
            continue

        dest = uploads_dir / src.name
        try:
            if dest.exists():
                # Avoid redundant copy — skip if same size
                if dest.stat().st_size == src.stat().st_size:
                    logger.debug("_sync_workspace_files_to_uploads: already synced %s", src.name)
                    continue
                dest.unlink()
            shutil.copy2(src, dest)
            logger.info(
                "_sync_workspace_files_to_uploads: copied %s -> %s (size=%d)",
                src.name, dest, dest.stat().st_size,
            )
        except Exception as exc:
            logger.warning(
                "_sync_workspace_files_to_uploads: failed to copy %s: %s",
                src_path_str, exc,
            )


async def _enrich_conversation_artifacts(record: dict[str, Any]) -> dict[str, Any]:
    """Helper to query and inject artifact metadata into a conversation record."""
    try:
        from app.gateway.services_v1.artifact_service import artifact_service
        thread_id = record["thread_id"]
        arts = await artifact_service.list_conversation_artifacts(thread_id)
        if arts:
            metadata = record.get("metadata") or {}
            metadata["_v1_artifacts"] = [
                {
                    "artifact_id": art.artifact_id,
                    "artifact_type": art.artifact_type,
                    "name": art.name,
                    "status": art.status,
                    "created_at": art.created_at.isoformat(),
                    "files": [
                        {
                            "file_id": f.file_id,
                            "format": f.file_format,
                            "filename": f.filename,
                            "url": f.download_url,
                        }
                        for f in art.files
                    ]
                }
                for art in arts
            ]
            record["metadata"] = metadata
    except Exception as e:
        logger.warning("Failed to enrich conversation %s with artifacts: %s", record.get("thread_id"), e)
    return record


def _normalize_agent_id(agent_id: str | None) -> str | None:
    if agent_id == "lead_agent":
        return "lead-agent"
    return agent_id


def _message_role(row: dict[str, Any]) -> str:
    event_type = str(row.get("event_type") or row.get("role") or "")
    # RunJournal writes "llm.human.input" / "llm.ai.response" for message events
    if event_type in ("human_message", "human", "user", "llm.human.input"):
        return "user"
    if event_type in ("ai_message", "ai", "assistant", "llm.ai.response"):
        return "assistant"
    if event_type in ("tool_message", "tool", "llm.tool.result"):
        return "tool"
    return "system"


def _extract_content(raw: Any) -> str:
    """Extract plain text content from an event store row.

    RunJournal writes ``message.model_dump()`` (a dict) as the content
    for human/ai/tool events, not a plain string.  When the content is a
    dict with a ``content`` key, use that inner value.
    """
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        inner = raw.get("content", "")
        if isinstance(inner, str):
            return inner
        if isinstance(inner, list):
            # OpenAI-style content blocks: [{"type": "text", "text": "..."}]
            texts = [part.get("text", "") for part in inner if isinstance(part, dict) and part.get("type") == "text"]
            return " ".join(texts)
        return str(inner)
    if isinstance(raw, list):
        texts = [part.get("text", "") for part in raw if isinstance(part, dict) and part.get("type") == "text"]
        return " ".join(texts)
    return str(raw)


def row_to_message(row: dict[str, Any]) -> MessageDTO:
    metadata = dict(row.get("metadata") or {})
    if feedback := row.get("feedback"):
        metadata["feedback"] = feedback
    return MessageDTO(
        message_id=str(row.get("id") or row.get("message_id") or row.get("seq") or "") or None,
        run_id=row.get("run_id"),
        role=_message_role(row),
        content=_extract_content(row.get("content")),
        created_at=coerce_iso(row.get("created_at") or row.get("timestamp") or ""),
        metadata=metadata,
    )


def record_to_conversation(record: dict[str, Any], *, last_message: MessageDTO | None = None) -> ConversationDTO:
    metadata = record.get("metadata") or {}
    return ConversationDTO(
        conversation_id=record["thread_id"],
        agent_id=_normalize_agent_id(record.get("assistant_id")),
        title=record.get("display_name") or metadata.get("title"),
        status=record.get("status", "idle"),
        last_message=last_message,
        created_at=coerce_iso(record.get("created_at", "")),
        updated_at=coerce_iso(record.get("updated_at", "")),
        metadata=metadata,
    )


async def create_conversation(request: Request, body: ConversationCreateRequest, context: ExternalContext) -> ConversationDTO:
    thread_store = get_thread_store(request)
    checkpointer = get_checkpointer(request)
    conversation_id = str(uuid.uuid4())
    metadata = build_external_metadata(context, body.metadata)
    if body.title:
        metadata.setdefault("title", body.title)
    record = await thread_store.create(conversation_id, assistant_id=body.agent_id, display_name=body.title, metadata=metadata)
    await checkpointer.aput(
        {"configurable": {"thread_id": conversation_id, "checkpoint_ns": ""}},
        empty_checkpoint(),
        {"step": -1, "source": "input", "writes": None, "parents": {}, "created_at": now_iso(), **metadata},
        {},
    )
    return record_to_conversation(record)


async def list_conversations(request: Request, *, limit: int, offset: int, status: str | None = None, metadata: dict[str, Any] | None = None) -> ConversationListResponse:
    thread_store = get_thread_store(request)
    event_store = get_run_event_store(request)
    search_limit = offset + limit + 1
    rows = await thread_store.search(status=status, limit=search_limit, offset=0)
    if metadata:
        rows = [row for row in rows if all((row.get("metadata") or {}).get(key) == value for key, value in metadata.items())]
    rows = rows[offset : offset + limit + 1]
    items = []
    for row in rows[:limit]:
        last_message = None
        try:
            messages = await event_store.list_messages(row["thread_id"], limit=1)
            if messages:
                last_message = row_to_message(messages[-1])
        except Exception:
            last_message = None
        
        row = await _enrich_conversation_artifacts(row)
        items.append(record_to_conversation(row, last_message=last_message))
    return ConversationListResponse(items=items, pagination=PaginationDTO(limit=limit, offset=offset, has_more=len(rows) > limit))


async def get_conversation(request: Request, conversation_id: str) -> ConversationDTO:
    thread_store = get_thread_store(request)
    record = await thread_store.get(conversation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    record = await _enrich_conversation_artifacts(record)
    return record_to_conversation(record)


async def update_conversation(request: Request, conversation_id: str, body: ConversationUpdateRequest) -> ConversationDTO:
    thread_store = get_thread_store(request)
    if body.metadata:
        await thread_store.update_metadata(conversation_id, body.metadata)
    if body.title:
        await thread_store.update_display_name(conversation_id, body.title)
    return await get_conversation(request, conversation_id)


async def delete_conversation(request: Request, conversation_id: str) -> None:
    thread_store = get_thread_store(request)
    checkpointer = get_checkpointer(request)
    if hasattr(checkpointer, "adelete_thread"):
        await checkpointer.adelete_thread(conversation_id)
    await thread_store.delete(conversation_id)


async def sync_artifacts_from_checkpoint(request: Request, conversation_id: str, run_id: str) -> None:
    """Sync artifacts from checkpoint state into the artifact store."""
    try:
        from app.gateway.services_v1.artifact_service import artifact_service

        checkpointer = get_checkpointer(request)
        if checkpointer is None:
            return

        config = {"configurable": {"thread_id": conversation_id, "checkpoint_ns": ""}}
        ckpt_tuple = await checkpointer.aget_tuple(config)
        if ckpt_tuple is None:
            return

        checkpoint = ckpt_tuple.checkpoint or {}
        channel_values = checkpoint.get("channel_values", {})
        artifacts = channel_values.get("artifacts", [])
        if not artifacts and isinstance(channel_values, dict):
            for val in channel_values.values():
                if isinstance(val, dict) and "artifacts" in val:
                    artifacts = val["artifacts"]
                    break

        for art in (artifacts or []):
            if isinstance(art, dict):
                await artifact_service.create_artifact(
                    conversation_id=conversation_id,
                    name=art.get("name", f"artifact_{run_id[:8]}"),
                    artifact_type=art.get("type", "file"),
                    run_id=run_id,
                    meta_json=art.get("metadata", {}),
                )
            elif isinstance(art, str) and art:
                # String artifact paths from present_files tool
                filename = PurePosixPath(art).name or "artifact"
                await artifact_service.create_artifact(
                    conversation_id=conversation_id,
                    name=filename,
                    artifact_type="file",
                    run_id=run_id,
                    meta_json={"source": "present_files", "path": art},
                )
    except Exception as e:
        logger.warning("Failed to sync artifacts from checkpoint: %s", e)


async def list_messages(request: Request, conversation_id: str, *, limit: int, before_seq: int | None = None, after_seq: int | None = None) -> ConversationMessagesResponse:
    event_store = get_run_event_store(request)
    rows = await event_store.list_messages(conversation_id, limit=limit + 1, before_seq=before_seq, after_seq=after_seq)
    return ConversationMessagesResponse(
        conversation_id=conversation_id,
        items=[row_to_message(row) for row in rows[:limit]],
        pagination=PaginationDTO(limit=limit, has_more=len(rows) > limit),
    )


async def send_message(request: Request, conversation_id: str, body: ConversationMessageRequest, context: ExternalContext):
    logger.info("=== send_message: conversation_id=%s, content=%.80s", conversation_id, body.content)

    selected_data_sources = await resolve_selected_data_sources(request, conversation_id, body.datasource_ids, max_context_tokens=body.options.max_context_tokens)
    logger.info("resolve_selected_data_sources returned %d items", len(selected_data_sources))
    if selected_data_sources:
        for ds in selected_data_sources:
            logger.info("  data_source: id=%s type=%s name=%s", ds.get("datasource_id"), ds.get("type"), ds.get("name"))

    # Also resolve workspace-attached data sources and merge
    workspace_sources = await resolve_workspace_data_sources(conversation_id)
    if workspace_sources:
        existing_ids = {ds.get("datasource_id") for ds in selected_data_sources}
        for ws in workspace_sources:
            if ws.get("datasource_id") not in existing_ids:
                selected_data_sources.append(ws)
                existing_ids.add(ws.get("datasource_id"))
        logger.info(
            "send_message: merged %d workspace data sources for conversation %s (total=%d)",
            len(workspace_sources), conversation_id, len(selected_data_sources),
        )

    # ════════════════════════════════════════════════════════════════
    # Copy workspace file-type data sources into sandbox uploads dir
    # so the LLM sees them in <uploaded_files> and via `ls /mnt/...`
    # ════════════════════════════════════════════════════════════════
    user_id = request.headers.get("x-user-id", "anonymous")
    if selected_data_sources and user_id:
        _sync_workspace_files_to_uploads(selected_data_sources, conversation_id, user_id)

    run_body = build_run_create_request(body, context, selected_data_sources=selected_data_sources)
    logger.info("run_body: assistant_id=%s context_keys=%s stream_mode=%s", run_body.assistant_id, list(run_body.context or {}), run_body.stream_mode)

    record = await start_run(run_body, conversation_id, request)
    logger.info("run started: run_id=%s status=%s", record.run_id, record.status)

    completed = True
    if record.task is not None:
        completed = await wait_for_run_completion(getattr(request.app.state, "stream_bridge"), record, request, get_run_manager(request))
    status = record.status.value if completed else "interrupted"
    logger.info("run completed: completed=%s status=%s total_tokens=%d output_tokens=%d", completed, status, record.total_tokens, record.total_output_tokens)

    message = None
    try:
        event_store = get_run_event_store(request)
        rows = await event_store.list_messages_by_run(conversation_id, record.run_id, limit=100)
        logger.info("event_store.list_messages_by_run returned %d rows", len(rows))
        for row in rows:
            logger.info("  msg event_type=%s role=%s content=%.80s", row.get("event_type"), _message_role(row), str(row.get("content", ""))[:80])

        ai_rows = [row for row in rows if _message_role(row) == "assistant"]
        logger.info("ai_rows count=%d", len(ai_rows))
        if ai_rows:
            message = row_to_message(ai_rows[-1])
            logger.info("returning message: message_id=%s content=%.80s", message.message_id, message.content[:80] if message.content else "")
    except Exception as e:
        logger.exception("Error reading messages from event store: %s", e)
        message = None
    from app.gateway.schemas.v1.conversations import ConversationMessageResponse

    return ConversationMessageResponse(
        run_id=record.run_id,
        conversation_id=conversation_id,
        agent_id=_normalize_agent_id(record.assistant_id),
        status=status,
        message=message,
        usage=UsageDTO(input_tokens=record.total_input_tokens, output_tokens=record.total_output_tokens, total_tokens=record.total_tokens),
    )


async def list_conversation_runs(request: Request, conversation_id: str) -> ConversationRunsResponse:
    run_manager = get_run_manager(request)
    records = await run_manager.list_by_thread(conversation_id)
    items = [
        RunDTO(
            run_id=record.run_id,
            conversation_id=record.thread_id,
            agent_id=_normalize_agent_id(record.assistant_id),
            status=record.status.value,
            created_at=record.created_at,
            updated_at=record.updated_at,
            usage=UsageDTO(input_tokens=record.total_input_tokens, output_tokens=record.total_output_tokens, total_tokens=record.total_tokens),
            error=record.error,
            metadata=record.metadata or {},
        )
        for record in records
    ]
    return ConversationRunsResponse(conversation_id=conversation_id, items=items)
