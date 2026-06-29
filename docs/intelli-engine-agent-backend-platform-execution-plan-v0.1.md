# intelli-engine Agent Backend Platform Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `/api/v1` as an external Agent Backend Adapter so other frontend/business teams can call intelli-engine for conversations, agents, selected data-source Q&A, report generation, artifacts, and AI logo/image generation.

**Architecture:** Add a new v1 adapter layer under `backend/app/gateway` without rewriting the existing DeerFlow/LangGraph runtime. The v1 layer translates external concepts (`conversation_id`, `agent_id`, `datasource_ids`, `artifact_id`) into current internal concepts (`thread_id`, `assistant_id`, `RunCreateRequest`, thread artifacts) and normalizes responses/SSE events for external consumers.

**Tech Stack:** FastAPI, Pydantic, LangGraph, existing `app.gateway.services.start_run`, `RunManager`, `StreamBridge`, `ThreadMetaStore`, `RunEventStore`, `Checkpointer`, pytest, ruff.

---

## 1. Scope

This plan implements the platform in phases. The first four phases are the minimum needed for the external frontend team to build a chat/agent product. Later phases add selected data-source Q&A, PDF/DOCX report generation, artifact registry, and AI Logo image generation.

Primary design references:

- `docs/intelli-engine-agent-backend-platform-design.md`
- `docs/intelli-engine-agent-backend-platform-design-v0.2.md`

Current internal code to reuse:

- `backend/app/gateway/app.py`
- `backend/app/gateway/services.py`
- `backend/app/gateway/routers/threads.py`
- `backend/app/gateway/routers/thread_runs.py`
- `backend/app/gateway/routers/runs.py`
- `backend/app/gateway/routers/agents.py`
- `backend/app/gateway/routers/artifacts.py`
- `backend/app/gateway/routers/uploads.py`
- `backend/packages/harness/deerflow/agents/lead_agent/agent.py`
- `backend/packages/harness/deerflow/runtime/runs/worker.py`
## 1.1 Implementation Status

Status as of 2026-06-23:

- Phase 1 completed: `/api/v1` router shell, shared DTOs, external header context, metadata merge, route mounting, and OpenAPI visibility are implemented.
- Phase 2 completed: conversation create/list/get/update/delete endpoints are implemented by adapting external `conversation_id` to existing thread metadata storage.
- Phase 3 completed: message history normalization, non-streaming send, streaming send, run request adapter, and normalized SSE event mapper are implemented.
- Phase 4 completed: agent list/invoke/stream endpoints, run get/cancel endpoints, and conversation run list endpoint are implemented.
- Phase 5 completed: data-source registration/listing and selected `datasource_ids` resolution into controlled run context are implemented. User message `content` remains unchanged; selected sources are passed through run metadata/context.
- Phase 9 completed for the implemented v1 surface: every implemented endpoint is mounted under FastAPI and appears in `/docs` and `/openapi.json` with v1 tags, summaries, descriptions, and response models where applicable.

Implementation note: the original plan named `backend/app/gateway/services/v1/`, but the repository already has `backend/app/gateway/services.py`. The implemented service adapter package is therefore `backend/app/gateway/v1_services/` to avoid a Python module/package collision.

## 2. File Structure

Create these v1 API files:

```text
backend/app/gateway/routers/v1/
  __init__.py
  conversations.py
  agents.py
  runs.py
  capabilities.py
  data_sources.py
  reports.py
  artifacts.py
  ai_logo.py

backend/app/gateway/schemas/v1/
  __init__.py
  common.py
  conversations.py
  agents.py
  runs.py
  capabilities.py
  data_sources.py
  reports.py
  artifacts.py
  ai_logo.py

backend/app/gateway/v1_services/
  __init__.py
  external_context.py
  run_adapter.py
  sse_mapper.py
  conversation_service.py
  agent_service.py
  run_service.py
  data_source_service.py
  report_service.py
  artifact_service.py
  logo_service.py
```

Modify:

```text
backend/app/gateway/app.py
```

Add tests:

```text
backend/tests/test_v1_external_context.py
backend/tests/test_v1_run_adapter.py
backend/tests/test_v1_conversations.py
backend/tests/test_v1_conversation_messages.py
backend/tests/test_v1_conversation_runs.py
backend/tests/test_v1_agents.py
backend/tests/test_v1_runs.py
backend/tests/test_v1_sse_mapper.py
backend/tests/test_v1_capabilities.py
backend/tests/test_v1_data_sources.py
backend/tests/test_v1_reports.py
backend/tests/test_v1_artifacts.py
backend/tests/test_v1_ai_logo.py
backend/tests/test_v1_openapi.py
```

## 3. Phase 1 - v1 Foundation

**Purpose:** Create the external API foundation, shared schemas, request context, route mounting, and online API documentation.

### Task 1.1: Create v1 shared schemas

**Files:**

- Create: `backend/app/gateway/schemas/v1/__init__.py`
- Create: `backend/app/gateway/schemas/v1/common.py`
- Test: `backend/tests/test_v1_external_context.py`

- [ ] Define common DTOs:
  - `ErrorDTO`
  - `ErrorResponse`
  - `PaginationDTO`
  - `UsageDTO`
  - `MessageDTO`
  - `ArtifactDTO`
  - `RunStatusDTO`

- [ ] Use field names that external teams can understand:
  - `conversation_id`
  - `agent_id`
  - `run_id`
  - `artifact_id`
  - `datasource_id`
  - `report_id`

- [ ] Do not expose internal names in v1 DTOs:
  - `thread_id`
  - `checkpoint`
  - `channel_values`
  - `RunnableConfig`
  - `configurable`
  - `stream_mode`

- [ ] Add unit tests validating DTO serialization for message, usage, pagination, and errors.

Run:

```bash
cd backend
uv run pytest tests/test_v1_external_context.py -v
```

Expected:

```text
PASS
```

### Task 1.2: Implement ExternalContext

**Files:**

- Create: `backend/app/gateway/v1_services/__init__.py`
- Create: `backend/app/gateway/v1_services/external_context.py`
- Test: `backend/tests/test_v1_external_context.py`

- [ ] Parse these headers:
  - `X-App-Id`
  - `X-API-Key`
  - `X-Request-Id`
  - `X-User-Id`

- [ ] Define `ExternalContext` with:
  - `app_id`
  - `api_key`
  - `request_id`
  - `external_user_id`

- [ ] Validate required fields:
  - `X-App-Id` required.
  - `X-API-Key` required for external calls.
  - `X-Request-Id` optional but echoed when present.
  - `X-User-Id` optional but should flow into metadata/context when present.

- [ ] Provide a helper to merge external context into metadata:

```text
metadata.app_id
metadata.external_user_id
metadata.request_id
```

- [ ] Provide a helper to merge external user into run context:

```text
context.user_id = external_user_id
```

- [ ] Add tests for missing app id, missing API key, optional user id, and metadata merge.

Run:

```bash
cd backend
uv run pytest tests/test_v1_external_context.py -v
```

Expected:

```text
PASS
```

### Task 1.3: Create v1 router shell and mount it

**Files:**

- Create: `backend/app/gateway/routers/v1/__init__.py`
- Create: `backend/app/gateway/routers/v1/capabilities.py`
- Modify: `backend/app/gateway/app.py`
- Test: `backend/tests/test_v1_openapi.py`

- [ ] Create `APIRouter(prefix="/api/v1")` in `routers/v1/__init__.py`.

- [ ] Include child routers as they are implemented.

- [ ] Add a minimal `GET /api/v1/capabilities` endpoint returning static capability flags for phase 1:

```json
{
  "conversation": {
    "streaming": true,
    "multi_turn": true
  },
  "agents": {
    "invoke": true,
    "stream": true
  },
  "data_sources": {
    "selected_ids_in_message": true
  },
  "reports": {
    "enabled": false
  },
  "logo": {
    "image_generate": false
  }
}
```

- [ ] Mount v1 router in `backend/app/gateway/app.py`.

- [ ] Ensure `/docs` and `/openapi.json` include v1 routes.

- [ ] Use OpenAPI tags:
  - `v1-capabilities`
  - later `v1-conversations`, `v1-agents`, `v1-runs`, etc.

Run:

```bash
cd backend
uv run pytest tests/test_v1_openapi.py tests/test_v1_capabilities.py -v
```

Expected:

```text
PASS
```

## 4. Phase 2 - Conversation Management

**Purpose:** Wrap current `threads` functionality as external `conversations` functionality for frontend teams.

### Task 2.1: Define conversation schemas

**Files:**

- Create: `backend/app/gateway/schemas/v1/conversations.py`
- Test: `backend/tests/test_v1_conversations.py`

- [ ] Define:
  - `ConversationCreateRequest`
  - `ConversationUpdateRequest`
  - `ConversationDTO`
  - `ConversationListResponse`
  - `ConversationMessageRequest`
  - `ConversationMessageResponse`
  - `ConversationMessagesResponse`
  - `ConversationRunsResponse`

- [ ] Include `datasource_ids` in `ConversationMessageRequest`:

```json
{
  "agent_id": "lead-agent",
  "content": "请基于选中的数据源总结风险�?,
  "datasource_ids": ["ds_001", "ds_002"],
  "options": {
    "model": "default",
    "thinking_enabled": true,
    "subagent_enabled": false,
    "citation_required": true,
    "max_context_tokens": 8000
  },
  "metadata": {
    "project_id": "p_001"
  }
}
```

- [ ] Do not expose `thread_id` in public schemas.

### Task 2.2: Implement conversation service

**Files:**

- Create: `backend/app/gateway/v1_services/conversation_service.py`
- Test: `backend/tests/test_v1_conversations.py`

- [ ] Implement `create_conversation`.

Internal mapping:

```text
conversation_id = thread_id
ThreadMetaStore.create()
checkpointer.aput(empty_checkpoint())
```

- [ ] Implement `list_conversations`.

Internal mapping:

```text
ThreadMetaStore.search()
run_event_store.list_messages(thread_id, limit=1) for last_message
```

- [ ] Implement `get_conversation`.

Internal mapping:

```text
ThreadMetaStore.get()
checkpointer.aget_tuple()
```

- [ ] Implement `update_conversation`.

Internal mapping:

```text
ThreadMetaStore.update_metadata()
ThreadMetaStore.update_display_name() for title
```

- [ ] Implement `delete_conversation`.

Internal mapping:

```text
delete local thread data
checkpointer.adelete_thread()
ThreadMetaStore.delete()
```

- [ ] Add tests for create/list/get/update/delete.

### Task 2.3: Implement conversation router

**Files:**

- Create: `backend/app/gateway/routers/v1/conversations.py`
- Modify: `backend/app/gateway/routers/v1/__init__.py`
- Test: `backend/tests/test_v1_conversations.py`

- [ ] Add routes:

```http
GET    /api/v1/conversations
POST   /api/v1/conversations
GET    /api/v1/conversations/{conversation_id}
PATCH  /api/v1/conversations/{conversation_id}
DELETE /api/v1/conversations/{conversation_id}
```

- [ ] Add OpenAPI summaries and descriptions.

- [ ] Ensure returned JSON uses `conversation_id`, not `thread_id`.

Run:

```bash
cd backend
uv run pytest tests/test_v1_conversations.py tests/test_v1_openapi.py -v
```

Expected:

```text
PASS
```

## 5. Phase 3 - Conversation Messages and Streaming

**Purpose:** Support non-streaming and streaming chat with optional selected data sources.

### Task 3.1: Implement run adapter

**Files:**

- Create: `backend/app/gateway/v1_services/run_adapter.py`
- Test: `backend/tests/test_v1_run_adapter.py`

- [ ] Convert `ConversationMessageRequest` to current `RunCreateRequest`.

External request:

```json
{
  "agent_id": "brand-agent",
  "content": "请总结风险�?,
  "datasource_ids": ["ds_001"],
  "options": {
    "model": "default",
    "thinking_enabled": true,
    "subagent_enabled": false
  },
  "metadata": {
    "project_id": "p_001"
  }
}
```

Internal request:

```json
{
  "assistant_id": "brand-agent",
  "input": {
    "messages": [
      {
        "role": "user",
        "content": "请总结风险�?
      }
    ]
  },
  "metadata": {
    "project_id": "p_001",
    "datasource_ids": ["ds_001"]
  },
  "context": {
    "model_name": "default",
    "thinking_enabled": true,
    "subagent_enabled": false
  },
  "stream_mode": ["values", "messages"]
}
```

- [ ] Preserve external context:
  - `app_id`
  - `external_user_id`
  - `request_id`

- [ ] Do not embed data-source content into `content`.

- [ ] Add tests for `agent_id`, `content`, `datasource_ids`, `options`, metadata merge, and external context merge.

### Task 3.2: Implement message history adapter

**Files:**

- Modify: `backend/app/gateway/v1_services/conversation_service.py`
- Test: `backend/tests/test_v1_conversation_messages.py`

- [ ] Implement `list_conversation_messages`.

Internal mapping:

```text
run_event_store.list_messages(thread_id, limit, before_seq, after_seq)
```

- [ ] Convert internal event/message types:

```text
human_message -> role=user
ai_message    -> role=assistant
tool_message  -> role=tool
system        -> role=system
```

- [ ] Return normalized message DTOs with:
  - `message_id`
  - `run_id`
  - `role`
  - `content`
  - `created_at`
  - `metadata`

### Task 3.3: Implement non-streaming send message

**Files:**

- Modify: `backend/app/gateway/v1_services/conversation_service.py`
- Modify: `backend/app/gateway/routers/v1/conversations.py`
- Test: `backend/tests/test_v1_conversation_messages.py`

- [ ] Add route:

```http
POST /api/v1/conversations/{conversation_id}/messages
```

- [ ] Use `run_adapter` to build `RunCreateRequest`.

- [ ] Call existing:

```text
start_run()
wait_for_run_completion()
```

- [ ] Extract final assistant message:
  1. Prefer `run_event_store.list_messages_by_run(thread_id, run_id)`.
  2. Fallback to latest checkpoint `channel_values.messages`.

- [ ] Return:
  - `run_id`
  - `conversation_id`
  - `agent_id`
  - `status`
  - final assistant `message`
  - `usage`
  - `artifacts`

### Task 3.4: Implement SSE mapper

**Files:**

- Create: `backend/app/gateway/v1_services/sse_mapper.py`
- Test: `backend/tests/test_v1_sse_mapper.py`

- [ ] Map internal events to v1 events:

```text
metadata -> run.started
messages -> message.delta
error    -> run.failed
end      -> run.completed
```

- [ ] Do not expose internal `values`, `messages`, `custom`, or raw LangGraph payload shapes.

- [ ] First phase event set:

```text
run.started
message.delta
run.completed
run.failed
```

- [ ] Add tests for each mapping.

### Task 3.5: Implement streaming send message

**Files:**

- Modify: `backend/app/gateway/v1_services/conversation_service.py`
- Modify: `backend/app/gateway/routers/v1/conversations.py`
- Test: `backend/tests/test_v1_sse_mapper.py`

- [ ] Add route:

```http
POST /api/v1/conversations/{conversation_id}/stream
```

- [ ] Use `start_run()`.

- [ ] Subscribe to `StreamBridge`.

- [ ] Convert stream entries through `sse_mapper`.

- [ ] Return `StreamingResponse` with `text/event-stream`.

Run:

```bash
cd backend
uv run pytest tests/test_v1_run_adapter.py tests/test_v1_conversation_messages.py tests/test_v1_sse_mapper.py -v
```

Expected:

```text
PASS
```

## 6. Phase 4 - Agent and Run APIs

**Purpose:** Let external teams query available agents, invoke agents directly, and manage run status.

### Task 4.1: Implement agent schemas and service

**Files:**

- Create: `backend/app/gateway/schemas/v1/agents.py`
- Create: `backend/app/gateway/v1_services/agent_service.py`
- Test: `backend/tests/test_v1_agents.py`

- [ ] Define:
  - `AgentDTO`
  - `AgentListResponse`
  - `AgentInvokeRequest`
  - `AgentInvokeResponse`

- [ ] Return system and custom agents:

```text
lead-agent
brand-agent
copywriting-agent
logo-agent
report-agent
```

- [ ] For custom agents, reuse `deerflow.config.agents_config.list_custom_agents()`.

- [ ] Do not return full `SOUL.md` in external list response.

### Task 4.2: Implement agent router

**Files:**

- Create: `backend/app/gateway/routers/v1/agents.py`
- Modify: `backend/app/gateway/routers/v1/__init__.py`
- Test: `backend/tests/test_v1_agents.py`

- [ ] Add:

```http
GET  /api/v1/agents
POST /api/v1/agents/{agent_id}/invoke
POST /api/v1/agents/{agent_id}/stream
```

- [ ] For invoke:
  - Create temporary conversation/thread.
  - Call `start_run()`.
  - Wait for completion.
  - Return normalized final response.

- [ ] For stream:
  - Create temporary conversation/thread.
  - Call `start_run()`.
  - Return normalized SSE.

### Task 4.3: Implement run schemas/service/router

**Files:**

- Create: `backend/app/gateway/schemas/v1/runs.py`
- Create: `backend/app/gateway/v1_services/run_service.py`
- Create: `backend/app/gateway/routers/v1/runs.py`
- Modify: `backend/app/gateway/routers/v1/__init__.py`
- Test: `backend/tests/test_v1_runs.py`

- [ ] Add:

```http
GET  /api/v1/runs/{run_id}
POST /api/v1/runs/{run_id}/cancel
```

- [ ] Map:

```text
RunRecord.thread_id -> conversation_id
RunRecord.assistant_id -> agent_id
RunRecord.status -> status
RunRecord token fields -> usage
```

- [ ] Cancel via:

```text
RunManager.cancel(run_id, action)
```

### Task 4.4: Implement conversation run list

**Files:**

- Modify: `backend/app/gateway/v1_services/conversation_service.py`
- Modify: `backend/app/gateway/routers/v1/conversations.py`
- Test: `backend/tests/test_v1_conversation_runs.py`

- [ ] Add:

```http
GET /api/v1/conversations/{conversation_id}/runs
```

- [ ] Use:

```text
RunManager.list_by_thread(thread_id)
```

- [ ] Return normalized run DTO list.

Run:

```bash
cd backend
uv run pytest tests/test_v1_agents.py tests/test_v1_runs.py tests/test_v1_conversation_runs.py -v
```

Expected:

```text
PASS
```

## 7. Phase 5 - Data Sources

**Purpose:** Support frontend-selected data sources in conversation requests without asking the frontend to concatenate source content into the prompt.

### Task 5.1: Define data-source schemas

**Files:**

- Create: `backend/app/gateway/schemas/v1/data_sources.py`
- Test: `backend/tests/test_v1_data_sources.py`

- [ ] Define:
  - `DataSourceCreateRequest`
  - `DataSourceDTO`
  - `DataSourceListResponse`

- [ ] Supported first-phase types:

```text
text
url
file
json
conversation
```

### Task 5.2: Implement data-source service

**Files:**

- Create: `backend/app/gateway/v1_services/data_source_service.py`
- Test: `backend/tests/test_v1_data_sources.py`

- [ ] Implement text data-source registration.

- [ ] Implement URL registration metadata.

- [ ] Design file data-source integration with current uploads:

```text
/api/threads/{thread_id}/uploads
```

- [ ] Store data-source metadata under conversation/thread scope.

- [ ] Keep raw content out of the user message `content`.

### Task 5.3: Implement data-source router

**Files:**

- Create: `backend/app/gateway/routers/v1/data_sources.py`
- Modify: `backend/app/gateway/routers/v1/__init__.py`
- Test: `backend/tests/test_v1_data_sources.py`

- [ ] Add:

```http
POST /api/v1/conversations/{conversation_id}/data-sources
GET  /api/v1/conversations/{conversation_id}/data-sources
```

### Task 5.4: Inject selected data-source context into runs

**Files:**

- Modify: `backend/app/gateway/v1_services/run_adapter.py`
- Modify: `backend/app/gateway/v1_services/data_source_service.py`
- Test: `backend/tests/test_v1_run_adapter.py`
- Test: `backend/tests/test_v1_data_sources.py`

- [ ] Given `datasource_ids`, resolve selected data sources.

- [ ] Build controlled context blocks:

```xml
<selected_data_sources>
  <source id="ds_001" name="项目尽调材料.pdf" type="pdf">
    <summary>...</summary>
    <relevant_chunks>
      <chunk id="ds_001#p3">...</chunk>
    </relevant_chunks>
  </source>
</selected_data_sources>
```

- [ ] Add selected source IDs to run metadata.

- [ ] Preserve original user `content` unchanged.

- [ ] Enforce `options.max_context_tokens`.

Run:

```bash
cd backend
uv run pytest tests/test_v1_data_sources.py tests/test_v1_run_adapter.py -v
```

Expected:

```text
PASS
```

## 8. Phase 6 - Reports: PDF/DOCX

**Purpose:** Generate formal reports from selected data sources and conversation Q&A.

### Task 6.1: Define report schemas

**Files:**

- Create: `backend/app/gateway/schemas/v1/reports.py`
- Test: `backend/tests/test_v1_reports.py`

- [ ] Define:
  - `ReportCreateRequest`
  - `ReportDTO`
  - `ReportArtifactDTO`
  - `ReportSpec`
  - `ReportSection`
  - `ReportContentBlock`
  - `CitationDTO`

- [ ] Support formats:

```text
docx
pdf
```

- [ ] Support report types:

```text
analysis
summary
research
meeting_notes
decision_memo
```

### Task 6.2: Implement report service

**Files:**

- Create: `backend/app/gateway/v1_services/report_service.py`
- Test: `backend/tests/test_v1_reports.py`

- [ ] Create report job records.

- [ ] Resolve:
  - conversation messages.
  - selected data sources.
  - report options.

- [ ] Use `report-agent` or equivalent model call to generate `ReportSpec`.

- [ ] Do not generate DOCX/PDF directly from free-form LLM text.

### Task 6.3: Implement DOCX renderer

**Files:**

- Modify: `backend/app/gateway/v1_services/report_service.py`
- Test: `backend/tests/test_v1_reports.py`

- [ ] Convert `ReportSpec` to DOCX.

- [ ] Use stable business-report styles.

- [ ] Include:
  - title.
  - metadata.
  - sections.
  - tables.
  - citations.

- [ ] Save to:

```text
/mnt/user-data/outputs/reports/{report_id}.docx
```

### Task 6.4: Implement PDF rendering

**Files:**

- Modify: `backend/app/gateway/v1_services/report_service.py`
- Test: `backend/tests/test_v1_reports.py`

- [ ] Prefer:

```text
DOCX -> PDF
```

- [ ] Provide fallback:

```text
ReportSpec -> reportlab PDF
```

- [ ] Save to:

```text
/mnt/user-data/outputs/reports/{report_id}.pdf
```

### Task 6.5: Implement report router

**Files:**

- Create: `backend/app/gateway/routers/v1/reports.py`
- Modify: `backend/app/gateway/routers/v1/__init__.py`
- Test: `backend/tests/test_v1_reports.py`

- [ ] Add:

```http
POST /api/v1/conversations/{conversation_id}/reports
GET  /api/v1/reports/{report_id}
```

- [ ] Return:
  - `report_id`
  - `run_id`
  - `conversation_id`
  - `status`
  - generated artifacts
  - summary

Run:

```bash
cd backend
uv run pytest tests/test_v1_reports.py -v
```

Expected:

```text
PASS
```

## 9. Phase 7 - Artifact Registry

**Purpose:** Hide thread virtual paths and expose stable artifact IDs for reports, logo images, and generated files.

### Task 7.1: Define artifact schemas

**Files:**

- Create: `backend/app/gateway/schemas/v1/artifacts.py`
- Test: `backend/tests/test_v1_artifacts.py`

- [ ] Define:
  - `ArtifactDTO`
  - `ArtifactListResponse`

### Task 7.2: Implement artifact service

**Files:**

- Create: `backend/app/gateway/v1_services/artifact_service.py`
- Test: `backend/tests/test_v1_artifacts.py`

- [ ] Implement mapping:

```text
artifact_id -> conversation_id/thread_id + virtual_path
```

- [ ] For phase 1, choose a stable reversible or persisted mapping.

- [ ] Long term, use database-backed registry:

```text
artifact_id
thread_id
run_id
virtual_path
filename
mime_type
created_at
metadata
```

### Task 7.3: Implement artifact router

**Files:**

- Create: `backend/app/gateway/routers/v1/artifacts.py`
- Modify: `backend/app/gateway/routers/v1/__init__.py`
- Test: `backend/tests/test_v1_artifacts.py`

- [ ] Add:

```http
GET /api/v1/artifacts/{artifact_id}
GET /api/v1/conversations/{conversation_id}/artifacts
```

- [ ] Internally reuse:

```text
/api/threads/{thread_id}/artifacts/{path}
```

- [ ] Do not expose `/mnt/user-data/outputs`.

Run:

```bash
cd backend
uv run pytest tests/test_v1_artifacts.py -v
```

Expected:

```text
PASS
```

## 10. Phase 8 - AI Logo Image Generation

**Purpose:** Generate logo/images from natural-language semantic requirements.

### Task 8.1: Define AI logo schemas

**Files:**

- Create: `backend/app/gateway/schemas/v1/ai_logo.py`
- Test: `backend/tests/test_v1_ai_logo.py`

- [ ] Define:
  - `LogoGenerateRequest`
  - `LogoGenerateOptions`
  - `LogoJobDTO`
  - `LogoDesignDTO`
  - `LogoAssetDTO`

- [ ] Request includes:

```json
{
  "input": "我想做一个面向年轻白领的精品咖啡品牌 logo，名字叫 Mellow Cup，希望简洁、有温度、不要太复杂",
  "options": {
    "style": "minimal",
    "count": 4,
    "size": "1024x1024",
    "transparent_background": true,
    "language": "zh-CN"
  },
  "metadata": {
    "project_id": "p_001"
  }
}
```

### Task 8.2: Implement logo service

**Files:**

- Create: `backend/app/gateway/v1_services/logo_service.py`
- Test: `backend/tests/test_v1_ai_logo.py`

- [ ] Build semantic design chain:

```text
natural language
-> brand understanding
-> visual direction
-> image prompt
-> image generation
-> artifact registration
```

- [ ] Use `logo-agent` or equivalent model call for design reasoning.

- [ ] Call image generation provider via `logo_generate` service/tool.

- [ ] Save images to outputs.

- [ ] Register generated image artifacts.

### Task 8.3: Implement AI logo router

**Files:**

- Create: `backend/app/gateway/routers/v1/ai_logo.py`
- Modify: `backend/app/gateway/routers/v1/__init__.py`
- Test: `backend/tests/test_v1_ai_logo.py`

- [ ] Add:

```http
POST /api/v1/ai/logo/generate
GET  /api/v1/ai/logo/jobs/{job_id}
```

- [ ] Return job first, not blocking HTTP until images complete.

Run:

```bash
cd backend
uv run pytest tests/test_v1_ai_logo.py -v
```

Expected:

```text
PASS
```

## 11. Phase 9 - Online API Documentation

**Purpose:** Ensure frontend/business teams can inspect and test the API via Swagger/OpenAPI.

### Task 9.1: Complete OpenAPI documentation

**Files:**

- Modify all `backend/app/gateway/routers/v1/*.py`
- Test: `backend/tests/test_v1_openapi.py`

- [ ] Add `summary` to every endpoint.

- [ ] Add `description` to every endpoint.

- [ ] Add `response_model` to every endpoint where possible.

- [ ] Add `responses` for common errors:
  - 400
  - 401
  - 403
  - 404
  - 409
  - 500
  - 503

- [ ] Use stable tags:
  - `v1-conversations`
  - `v1-agents`
  - `v1-runs`
  - `v1-data-sources`
  - `v1-reports`
  - `v1-artifacts`
  - `v1-ai-logo`
  - `v1-capabilities`

- [ ] Ensure `/docs` displays all v1 routes.

- [ ] Ensure `/openapi.json` can be imported by Apifox/Postman.

Run:

```bash
cd backend
uv run pytest tests/test_v1_openapi.py -v
```

Expected:

```text
PASS
```

## 12. Phase 10 - Final Verification

**Purpose:** Verify the complete v1 adapter without breaking existing APIs.

### Task 10.1: Run targeted tests

Run:

```bash
cd backend
uv run pytest tests/test_v1_*.py -v
```

Expected:

```text
PASS
```

### Task 10.2: Run backend lint

Run:

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
```

Expected:

```text
PASS
```

### Task 10.3: Run relevant existing tests

Run:

```bash
cd backend
uv run pytest tests/test_threads_router.py tests/test_runs_api_endpoints.py tests/test_artifacts_router.py tests/test_uploads_router.py tests/test_harness_boundary.py -v
```

Expected:

```text
PASS
```

### Task 10.4: Manual integration smoke

- [ ] Start gateway.

```bash
cd backend
make gateway
```

- [ ] Open Swagger:

```text
http://localhost:8001/docs
```

- [ ] Verify v1 routes are visible.

- [ ] Create conversation via `/api/v1/conversations`.

- [ ] Send non-streaming message via `/api/v1/conversations/{id}/messages`.

- [ ] Send streaming message via `/api/v1/conversations/{id}/stream`.

- [ ] Query conversation list.

- [ ] Query message history.

- [ ] Query run status.

- [ ] Cancel a long-running run.

- [ ] Register a text data source.

- [ ] Send message with `datasource_ids`.

- [ ] Generate a report.

- [ ] Download generated DOCX/PDF artifact.

- [ ] Submit AI logo generation job.

- [ ] Download generated image artifact.

## 13. Recommended Implementation Order

Implement in this order:

```text
1. Phase 1 - v1 Foundation
2. Phase 2 - Conversation Management
3. Phase 3 - Conversation Messages and Streaming
4. Phase 4 - Agent and Run APIs
5. Phase 5 - Data Sources
6. Phase 7 - Artifact Registry
7. Phase 6 - Reports: PDF/DOCX
8. Phase 8 - AI Logo Image Generation
9. Phase 9 - Online API Documentation polish
10. Phase 10 - Final Verification
```

Reasoning:

- Frontend teams need conversations, messages, streaming, and agents first.
- Data-source selected Q&A comes next because it changes message request semantics.
- Artifact registry should exist before reports and logos return files.
- Reports are higher enterprise value and should land before AI Logo if only one enhancement can be prioritized.
- AI Logo depends on async jobs, image provider integration, and artifact registry.

## 14. Phase Acceptance Checklist

### Phase 1-4 acceptance

- [ ] External team can list conversations.
- [ ] External team can create a conversation.
- [ ] External team can get conversation detail.
- [ ] External team can send a non-streaming message.
- [ ] External team can receive streaming deltas.
- [ ] External team can read message history.
- [ ] External team can list agents.
- [ ] External team can invoke an agent.
- [ ] External team can query and cancel runs.
- [ ] Swagger shows all phase 1-4 APIs.

### Phase 5 acceptance

- [ ] External team can register data sources.
- [ ] External team can select `datasource_ids` during chat.
- [ ] Backend injects data-source context, not frontend.
- [ ] Run metadata records selected data-source IDs.

### Phase 6-7 acceptance

- [ ] External team can create report generation job.
- [ ] Report job can generate DOCX.
- [ ] Report job can generate PDF.
- [ ] Report files are returned as artifacts.
- [ ] External team does not see internal virtual paths.

### Phase 8 acceptance

- [ ] External team can submit AI Logo generation job.
- [ ] Job performs semantic design reasoning.
- [ ] Job calls image generation provider.
- [ ] Generated images are returned as artifacts.

## 15. Out of Scope for First Delivery

Do not include in the first delivery:

- Browser-direct API key usage.
- Full tenant billing.
- Complex RBAC.
- Frontend UI changes.
- WebSocket replacement for SSE.
- External Agent creation/modification.
- Full enterprise artifact lifecycle policies.
- Advanced report template editor.
- Multi-provider image routing UI.

## 16. Commit Strategy

Use small commits by phase or task group:

```text
feat(v1): add external context and shared schemas
feat(v1): add conversation management endpoints
feat(v1): add conversation message and stream endpoints
feat(v1): add agent and run endpoints
feat(v1): add selected data source support
feat(v1): add artifact registry
feat(v1): add report generation endpoints
feat(v1): add ai logo generation endpoints
docs(v1): document external api contract
```

Before each commit:

```bash
cd backend
uv run pytest tests/test_v1_<area>.py -v
uv run ruff check .
```

Before final merge:

```bash
cd backend
make lint
make test
```
