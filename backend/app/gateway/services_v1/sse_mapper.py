from __future__ import annotations

from typing import Any


def _get_value(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _message_and_metadata(data: Any) -> tuple[Any, dict[str, Any]]:
    if isinstance(data, (list, tuple)) and data:
        message = data[0]
        metadata = _as_dict(data[1]) if len(data) > 1 else {}
        return message, metadata
    return data, {}


def _extract_delta(data: Any) -> str:
    chunk, _ = _message_and_metadata(data)
    content = _get_value(chunk, "content")
    if isinstance(content, str):
        return content
    if isinstance(chunk, dict):
        value = chunk.get("content") or chunk.get("delta") or chunk.get("text")
        return value if isinstance(value, str) else ""
    return chunk if isinstance(chunk, str) else ""


def _extract_reasoning_delta(message: Any) -> str:
    additional_kwargs = _as_dict(_get_value(message, "additional_kwargs"))
    for key in ("reasoning_content", "reasoning"):
        value = additional_kwargs.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _base_message_payload(message: Any, metadata: dict[str, Any], *, conversation_id: str, agent_id: str | None, delta: str, delta_type: str) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "agent_id": agent_id,
        "delta": delta,
        "delta_type": delta_type,
        "message_type": _get_value(message, "type"),
        "node": metadata.get("langgraph_node"),
        "model": metadata.get("model_name") or metadata.get("ls_model_name"),
        "provider": metadata.get("ls_provider") or _as_dict(_get_value(message, "response_metadata")).get("model_provider"),
        "thinking_enabled": metadata.get("thinking_enabled"),
        "raw_metadata": metadata,
    }


def map_stream_event(event: str, data: Any, *, conversation_id: str, agent_id: str | None) -> tuple[str, dict[str, Any]] | None:
    if event == "metadata":
        run_id = data.get("run_id") if isinstance(data, dict) else None
        return "run.started", {"run_id": run_id, "conversation_id": conversation_id, "agent_id": agent_id}
    if event == "messages":
        message, metadata = _message_and_metadata(data)
        message_type = _get_value(message, "type")
        if message_type in {"human", "HumanMessage", "HumanMessageChunk"}:
            return (
                "message.user",
                _base_message_payload(message, metadata, conversation_id=conversation_id, agent_id=agent_id, delta=_extract_delta(data), delta_type="user"),
            )
        if message_type == "tool":
            return (
                "tool.result",
                {
                    "conversation_id": conversation_id,
                    "agent_id": agent_id,
                    "tool_call_id": _get_value(message, "tool_call_id"),
                    "tool_name": _get_value(message, "name"),
                    "status": _get_value(message, "status"),
                    "content": _extract_delta(data),
                    "message_type": message_type,
                    "node": metadata.get("langgraph_node"),
                    "raw_metadata": metadata,
                },
            )
        delta = _extract_delta(data)
        reasoning_delta = _extract_reasoning_delta(message)
        tool_calls = _as_list(_get_value(message, "tool_calls"))
        tool_call_chunks = _as_list(_get_value(message, "tool_call_chunks"))
        invalid_tool_calls = _as_list(_get_value(message, "invalid_tool_calls"))
        if tool_calls or tool_call_chunks or invalid_tool_calls:
            payload = _base_message_payload(message, metadata, conversation_id=conversation_id, agent_id=agent_id, delta=delta, delta_type="tool_call")
            payload.update(
                {
                    "tool_calls": tool_calls,
                    "tool_call_chunks": tool_call_chunks,
                    "invalid_tool_calls": invalid_tool_calls,
                }
            )
            return "message.tool_call_delta", payload
        delta_type = "reasoning" if reasoning_delta and not delta else "answer"
        payload = _base_message_payload(message, metadata, conversation_id=conversation_id, agent_id=agent_id, delta=reasoning_delta if delta_type == "reasoning" else delta, delta_type=delta_type)
        return ("message.reasoning_delta" if delta_type == "reasoning" else "message.delta"), payload
    if event == "updates":
        return "agent.update", {"conversation_id": conversation_id, "agent_id": agent_id, "updates": data}
    if event == "values" and isinstance(data, dict) and (data.get("artifacts") or data.get("viewed_images")):
        return (
            "artifact.updated",
            {
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "artifacts": data.get("artifacts") or [],
                "viewed_images": data.get("viewed_images") or {},
            },
        )
    if event == "error":
        message = data.get("message") if isinstance(data, dict) else str(data)
        return "run.failed", {"conversation_id": conversation_id, "error": {"code": "RUN_FAILED", "message": message or "Run failed"}}
    if event == "end":
        return "run.completed", {"conversation_id": conversation_id, "status": "success"}
    return None
