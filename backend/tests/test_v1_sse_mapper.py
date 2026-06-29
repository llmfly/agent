import importlib.util
from pathlib import Path

_SSE_MAPPER_PATH = Path(__file__).parents[1] / "app" / "gateway" / "services_v1" / "sse_mapper.py"
_SSE_MAPPER_SPEC = importlib.util.spec_from_file_location("sse_mapper_under_test", _SSE_MAPPER_PATH)
assert _SSE_MAPPER_SPEC is not None
_SSE_MAPPER = importlib.util.module_from_spec(_SSE_MAPPER_SPEC)
assert _SSE_MAPPER_SPEC.loader is not None
_SSE_MAPPER_SPEC.loader.exec_module(_SSE_MAPPER)
map_stream_event = _SSE_MAPPER.map_stream_event


def test_sse_mapper_maps_metadata_to_run_started():
    mapped = map_stream_event("metadata", {"run_id": "run-1", "thread_id": "conv-1"}, conversation_id="conv-1", agent_id="agent-1")

    assert mapped == ("run.started", {"run_id": "run-1", "conversation_id": "conv-1", "agent_id": "agent-1"})


def test_sse_mapper_maps_string_message_chunk_to_delta():
    mapped = map_stream_event("messages", ["hello", {}], conversation_id="conv-1", agent_id="agent-1")

    assert mapped == (
        "message.delta",
        {
            "conversation_id": "conv-1",
            "agent_id": "agent-1",
            "delta": "hello",
            "delta_type": "answer",
            "message_type": None,
            "node": None,
            "model": None,
            "provider": None,
            "thinking_enabled": None,
            "raw_metadata": {},
        },
    )


def test_sse_mapper_preserves_message_semantics_for_answer_chunks():
    mapped = map_stream_event(
        "messages",
        [
            {
                "content": "server",
                "additional_kwargs": {},
                "response_metadata": {"model_provider": "deepseek"},
                "type": "AIMessageChunk",
            },
            {
                "langgraph_node": "model",
                "model_name": "deepseek-v4-flash",
                "thinking_enabled": False,
                "ls_provider": "deepseek",
            },
        ],
        conversation_id="conv-1",
        agent_id=None,
    )

    assert mapped == (
        "message.delta",
        {
            "conversation_id": "conv-1",
            "agent_id": None,
            "delta": "server",
            "delta_type": "answer",
            "message_type": "AIMessageChunk",
            "node": "model",
            "model": "deepseek-v4-flash",
            "provider": "deepseek",
            "thinking_enabled": False,
            "raw_metadata": {
                "langgraph_node": "model",
                "model_name": "deepseek-v4-flash",
                "thinking_enabled": False,
                "ls_provider": "deepseek",
            },
        },
    )


def test_sse_mapper_emits_reasoning_event_for_reasoning_chunks():
    mapped = map_stream_event(
        "messages",
        [
            {
                "content": "",
                "additional_kwargs": {"reasoning_content": "think first"},
                "type": "AIMessageChunk",
            },
            {
                "langgraph_node": "model",
                "model_name": "deepseek-r1",
                "thinking_enabled": True,
            },
        ],
        conversation_id="conv-1",
        agent_id="agent-1",
    )

    assert mapped == (
        "message.reasoning_delta",
        {
            "conversation_id": "conv-1",
            "agent_id": "agent-1",
            "delta": "think first",
            "delta_type": "reasoning",
            "message_type": "AIMessageChunk",
            "node": "model",
            "model": "deepseek-r1",
            "provider": None,
            "thinking_enabled": True,
            "raw_metadata": {
                "langgraph_node": "model",
                "model_name": "deepseek-r1",
                "thinking_enabled": True,
            },
        },
    )


def test_sse_mapper_distinguishes_user_message_echoes():
    mapped = map_stream_event(
        "messages",
        [
            {
                "content": "hello",
                "additional_kwargs": {},
                "type": "human",
            },
            {
                "langgraph_node": "DynamicContextMiddleware.before_agent",
                "model_name": "deepseek-v4-flash",
            },
        ],
        conversation_id="conv-1",
        agent_id=None,
    )

    assert mapped == (
        "message.user",
        {
            "conversation_id": "conv-1",
            "agent_id": None,
            "delta": "hello",
            "delta_type": "user",
            "message_type": "human",
            "node": "DynamicContextMiddleware.before_agent",
            "model": "deepseek-v4-flash",
            "provider": None,
            "thinking_enabled": None,
            "raw_metadata": {
                "langgraph_node": "DynamicContextMiddleware.before_agent",
                "model_name": "deepseek-v4-flash",
            },
        },
    )


def test_sse_mapper_emits_tool_call_delta_for_tool_call_chunks():
    mapped = map_stream_event(
        "messages",
        [
            {
                "content": "",
                "additional_kwargs": {},
                "type": "AIMessageChunk",
                "tool_call_chunks": [
                    {
                        "name": "web_search",
                        "args": '{"query":"hadoop"}',
                        "id": "call-1",
                        "index": 0,
                    }
                ],
            },
            {
                "langgraph_node": "model",
                "model_name": "deepseek-v4-flash",
                "thinking_enabled": False,
            },
        ],
        conversation_id="conv-1",
        agent_id=None,
    )

    assert mapped == (
        "message.tool_call_delta",
        {
            "conversation_id": "conv-1",
            "agent_id": None,
            "delta": "",
            "delta_type": "tool_call",
            "message_type": "AIMessageChunk",
            "node": "model",
            "model": "deepseek-v4-flash",
            "provider": None,
            "thinking_enabled": False,
            "tool_calls": [],
            "tool_call_chunks": [
                {
                    "name": "web_search",
                    "args": '{"query":"hadoop"}',
                    "id": "call-1",
                    "index": 0,
                }
            ],
            "invalid_tool_calls": [],
            "raw_metadata": {
                "langgraph_node": "model",
                "model_name": "deepseek-v4-flash",
                "thinking_enabled": False,
            },
        },
    )


def test_sse_mapper_emits_tool_result_for_tool_messages():
    mapped = map_stream_event(
        "messages",
        [
            {
                "content": "search result",
                "type": "tool",
                "name": "web_search",
                "tool_call_id": "call-1",
                "status": "success",
            },
            {
                "langgraph_node": "tools",
            },
        ],
        conversation_id="conv-1",
        agent_id="agent-1",
    )

    assert mapped == (
        "tool.result",
        {
            "conversation_id": "conv-1",
            "agent_id": "agent-1",
            "tool_call_id": "call-1",
            "tool_name": "web_search",
            "status": "success",
            "content": "search result",
            "message_type": "tool",
            "node": "tools",
            "raw_metadata": {"langgraph_node": "tools"},
        },
    )


def test_sse_mapper_maps_updates_to_agent_update():
    mapped = map_stream_event(
        "updates",
        {"SandboxMiddleware.before_agent": None},
        conversation_id="conv-1",
        agent_id=None,
    )

    assert mapped == (
        "agent.update",
        {
            "conversation_id": "conv-1",
            "agent_id": None,
            "updates": {"SandboxMiddleware.before_agent": None},
        },
    )


def test_sse_mapper_maps_values_artifacts_to_artifact_updated():
    mapped = map_stream_event(
        "values",
        {
            "messages": [],
            "artifacts": [{"id": "art-1", "kind": "image"}],
            "viewed_images": {"img-1": True},
        },
        conversation_id="conv-1",
        agent_id=None,
    )

    assert mapped == (
        "artifact.updated",
        {
            "conversation_id": "conv-1",
            "agent_id": None,
            "artifacts": [{"id": "art-1", "kind": "image"}],
            "viewed_images": {"img-1": True},
        },
    )


def test_sse_mapper_maps_error_and_end():
    assert map_stream_event("error", {"message": "boom"}, conversation_id="conv-1", agent_id=None) == (
        "run.failed",
        {"conversation_id": "conv-1", "error": {"code": "RUN_FAILED", "message": "boom"}},
    )
    assert map_stream_event("end", None, conversation_id="conv-1", agent_id=None) == (
        "run.completed",
        {"conversation_id": "conv-1", "status": "success"},
    )
