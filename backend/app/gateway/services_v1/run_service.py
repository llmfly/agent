from __future__ import annotations

import asyncio

from fastapi import HTTPException, Request

from app.gateway.deps import get_run_manager
from app.gateway.schemas.v1.common import RunDTO, UsageDTO


def _normalize_agent_id(agent_id: str | None) -> str | None:
    if agent_id == "lead_agent":
        return "lead-agent"
    return agent_id


def run_record_to_dto(record) -> RunDTO:
    return RunDTO(
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


async def get_run(request: Request, run_id: str) -> RunDTO:
    record = await get_run_manager(request).get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_record_to_dto(record)


async def cancel_run(request: Request, run_id: str, *, action: str, wait: bool = False) -> bool:
    run_manager = get_run_manager(request)
    record = await run_manager.get(run_id)
    cancelled = await run_manager.cancel(run_id, action=action)
    if cancelled and wait and record is not None and record.task is not None:
        try:
            await record.task
        except asyncio.CancelledError:
            pass
    return cancelled
