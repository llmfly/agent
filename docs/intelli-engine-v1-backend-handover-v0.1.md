# intelli-engine v1 Backend Handover Report

版本：v0.1  
日期：2026-06-23  
范围：`/api/v1` 后端能力交接说明  
状态：阶段性交付，未完成完整平台闭环

## 1. 交接结论

当前代码已经形成 `/api/v1` 后端适配层，可支撑外部前端团队进行会话、对话、Agent 调用、Run 查询/取消、数据源注册与选择的第一轮联调。

但它还不是完整智能体业务平台。报告生成、稳定 Artifact Registry、AI Logo 图片生成、远端 dev 非容器化部署脚本仍未完成。数据源能力目前完成到“注册、保存、选择、传递到 run context”，还缺少 agent prompt/middleware 层的显式注入闭环。

当前阶段判断：

| 阶段 | 当前状态 | 结论 |
|---|---:|---|
| Phase 1 v1 Foundation | 基本完成 | `/api/v1` 路由、DTO、Header 上下文、OpenAPI 基础已完成 |
| Phase 2 Conversation Management | 基本完成 | 会话 CRUD 已完成 |
| Phase 3 Conversation Messages and Streaming | 基本完成 | 消息历史、非流式、流式、SSE mapper 已完成 |
| Phase 4 Agent and Run APIs | 基本完成 | Agent list/invoke/stream、Run get/cancel 已完成 |
| Phase 5 Data Sources | 部分完成 | 注册、列表、选择、context 传递已完成；模型注入闭环未完成 |
| Phase 6 Reports PDF/DOCX | 未开始 | 无 reports v1 文件和测试 |
| Phase 7 Artifact Registry | 未开始 | 无 v1 artifact_id registry |
| Phase 8 AI Logo Image Generation | 未开始 | 无 ai_logo v1 文件和测试 |
| Phase 9 Online API Documentation | 部分完成 | 已实现接口进入 OpenAPI；未覆盖未实现模块和统一错误响应 |
| Phase 10 Final Verification / Deployment | 未完成 | 未完成远端 dev 非容器化部署与真实服务验收 |

## 2. 当前已落地代码

### 2.1 v1 路由层

已新增：

```text
backend/app/gateway/routers/v1/
  __init__.py
  capabilities.py
  conversations.py
  agents.py
  runs.py
  data_sources.py
```

事实依据：

- `/api/v1` 总路由定义在 `backend/app/gateway/routers/v1/__init__.py`。
- 已 include：`capabilities`、`conversations`、`agents`、`runs`、`data_sources`。
- Gateway 已在 `backend/app/gateway/app.py` 中引入并挂载 `v1.router`。

### 2.2 v1 Schema 层

已新增：

```text
backend/app/gateway/schemas/v1/
  __init__.py
  common.py
  capabilities.py
  conversations.py
  agents.py
  runs.py
  data_sources.py
```

对外字段采用外部团队可理解命名：

```text
conversation_id
agent_id
run_id
datasource_id
artifact_id
```

当前未新增：

```text
backend/app/gateway/schemas/v1/reports.py
backend/app/gateway/schemas/v1/artifacts.py
backend/app/gateway/schemas/v1/ai_logo.py
```

### 2.3 v1 Service 层

已新增：

```text
backend/app/gateway/v1_services/
  __init__.py
  external_context.py
  run_adapter.py
  sse_mapper.py
  conversation_service.py
  agent_service.py
  run_service.py
  data_source_service.py
```

注意：原执行计划曾写作 `backend/app/gateway/services/v1/`，但当前仓库已经存在 `backend/app/gateway/services.py` 单文件模块。为避免 Python module/package 冲突，实际实现路径调整为 `backend/app/gateway/v1_services/`。

当前未新增：

```text
backend/app/gateway/v1_services/report_service.py
backend/app/gateway/v1_services/artifact_service.py
backend/app/gateway/v1_services/logo_service.py
```

## 3. 当前已提供接口

### 3.1 能力发现

```text
GET /api/v1/capabilities
```

当前返回中：

```text
conversation.streaming = true
conversation.multi_turn = true
conversation.history = true
agents.invoke = true
agents.stream = true
data_sources.selected_ids_in_message = true
data_sources.registration = true
reports.enabled = false
logo.image_generate = false
```

### 3.2 会话接口

```text
GET    /api/v1/conversations
POST   /api/v1/conversations
GET    /api/v1/conversations/{conversation_id}
PATCH  /api/v1/conversations/{conversation_id}
DELETE /api/v1/conversations/{conversation_id}
```

说明：

- v1 对外使用 `conversation_id`。
- 内部复用现有 thread metadata store。
- 返回 DTO 不暴露 `thread_id`、`checkpoint`、`channel_values` 等内部字段。

### 3.3 对话和消息接口

```text
GET  /api/v1/conversations/{conversation_id}/messages
POST /api/v1/conversations/{conversation_id}/messages
POST /api/v1/conversations/{conversation_id}/stream
GET  /api/v1/conversations/{conversation_id}/runs
```

说明：

- 非流式发送复用现有 `start_run` / `wait_for_run_completion`。
- 流式发送通过 `StreamBridge` 订阅内部事件，再由 v1 SSE mapper 转成外部事件。
- 当前 v1 SSE 事件包括：
  - `run.started`
  - `message.delta`
  - `run.failed`
  - `run.completed`

### 3.4 Agent 接口

```text
GET  /api/v1/agents
POST /api/v1/agents/{agent_id}/invoke
POST /api/v1/agents/{agent_id}/stream
```

说明：

- `GET /agents` 返回 system agent 和 custom agent。
- custom agent 列表不暴露完整 `SOUL.md`。
- invoke/stream 当前使用临时 `conversation_id` 调用底层对话能力。

### 3.5 Run 接口

```text
GET  /api/v1/runs/{run_id}
POST /api/v1/runs/{run_id}/cancel
```

说明：

- 查询返回标准化 `RunDTO`。
- 取消当前返回 `cancel_requested`。

### 3.6 数据源接口

```text
POST /api/v1/conversations/{conversation_id}/data-sources
GET  /api/v1/conversations/{conversation_id}/data-sources
```

对话时选择数据源：

```text
POST /api/v1/conversations/{conversation_id}/messages
POST /api/v1/conversations/{conversation_id}/stream
```

请求体示例：

```json
{
  "agent_id": "lead-agent",
  "content": "请基于选中的数据源总结风险点",
  "datasource_ids": ["ds_xxxxx"],
  "options": {
    "model": "default",
    "citation_required": true,
    "max_context_tokens": 8000
  },
  "metadata": {
    "project_id": "p-001"
  }
}
```

重要约定：

- 前端不要把数据源正文拼入 `content`。
- 前端只传 `datasource_ids`。
- 后端根据 `datasource_ids` 解析数据源，并放入 run metadata/context。

## 4. Header 鉴权和上下文

v1 外部接口使用以下 Header：

```text
X-App-Id: required
X-API-Key: required
X-Request-Id: optional
X-User-Id: optional
```

当前实现事实：

- `X-App-Id` 缺失返回 401。
- `X-API-Key` 缺失返回 401。
- `X-Request-Id` 会写入 metadata。
- `X-User-Id` 会写入 metadata，并作为外部用户上下文参与 store 隔离。

注意：当前只是 Header 级别校验是否存在，并没有实现 API Key 的数据库校验、签名校验、租户密钥管理或权限模型。这是后续生产化必须补的点。

## 5. 测试和验证现状

当前新增测试：

```text
backend/tests/test_v1_external_context.py
backend/tests/test_v1_run_adapter.py
backend/tests/test_v1_sse_mapper.py
backend/tests/test_v1_capabilities.py
backend/tests/test_v1_conversations.py
backend/tests/test_v1_agents.py
backend/tests/test_v1_runs.py
backend/tests/test_v1_data_sources.py
backend/tests/test_v1_openapi.py
```

已验证结果：

```text
14 passed
ruff check: All checks passed
```

已覆盖：

- Header 缺失和 metadata merge。
- Run adapter 字段映射。
- SSE mapper 事件映射。
- capabilities 返回。
- 会话 CRUD。
- 消息历史 role 标准化。
- Agent list。
- Run get/cancel。
- 数据源注册、列表、选择顺序、预算截断。
- OpenAPI 包含部分 v1 路由。

未覆盖：

- 真实 LLM 调用。
- 真实流式端到端。
- 真实 Gateway 启动。
- 真实远端 dev 环境部署。
- 文件数据源上传与解析。
- URL 数据源抓取。
- 报告生成。
- Artifact 下载。
- AI Logo 图片生成。

## 6. 未完成任务明细

### 6.1 Phase 5 Data Sources 未完成项

已完成：

- 数据源注册。
- 数据源列表。
- `datasource_ids` 解析。
- 选中数据源按顺序进入 `selected_data_sources`。
- `max_context_tokens` 做粗略字符预算截断。
- `selected_data_sources` 加入 run context 白名单。

未完成：

- agent middleware 或 prompt 未显式读取 `selected_data_sources` 并注入模型上下文。
- `type=url` 只是保存 metadata/content，没有抓取网页内容。
- `type=file` 未和现有 uploads router 打通。
- `type=json` 没有结构化解析、摘要或 schema 校验。
- 没有数据源删除接口。
- 没有数据源更新接口。
- 没有大文本分块、索引、召回、引用定位。
- 没有 citation 结果结构化返回。

结论：Phase 5 目前是“接口与传递层部分完成”，不是“问答可完全基于数据源”的最终完成。

### 6.2 Phase 6 Reports PDF/DOCX 未开始

缺失文件：

```text
backend/app/gateway/routers/v1/reports.py
backend/app/gateway/schemas/v1/reports.py
backend/app/gateway/v1_services/report_service.py
backend/tests/test_v1_reports.py
```

缺失能力：

- `POST /api/v1/conversations/{conversation_id}/reports`
- `GET /api/v1/reports/{report_id}`
- 报告任务状态。
- 从对话和数据源生成 ReportSpec。
- DOCX 渲染。
- PDF 渲染。
- 报告文件保存。
- 报告 artifact 注册。

### 6.3 Phase 7 Artifact Registry 未开始

缺失文件：

```text
backend/app/gateway/routers/v1/artifacts.py
backend/app/gateway/schemas/v1/artifacts.py
backend/app/gateway/v1_services/artifact_service.py
backend/tests/test_v1_artifacts.py
```

当前事实：

- 仓库已有旧 artifact 接口：`/api/threads/{thread_id}/artifacts/{path}`。
- 但 v1 还没有稳定 `artifact_id`。
- 外部团队仍不能通过 v1 使用稳定 artifact ID 下载报告、Logo 或生成文件。

缺失能力：

- `GET /api/v1/artifacts/{artifact_id}`
- `GET /api/v1/conversations/{conversation_id}/artifacts`
- 内部 path 到 `artifact_id` 的映射。
- 隐藏 `/mnt/user-data/outputs` 等内部路径。

### 6.4 Phase 8 AI Logo 未开始

缺失文件：

```text
backend/app/gateway/routers/v1/ai_logo.py
backend/app/gateway/schemas/v1/ai_logo.py
backend/app/gateway/v1_services/logo_service.py
backend/tests/test_v1_ai_logo.py
```

缺失能力：

- `POST /api/v1/ai/logo/generate`
- `GET /api/v1/ai/logo/jobs/{job_id}`
- Logo 语义理解。
- Logo 设计规格生成。
- 图片生成 provider 调用。
- 图片保存。
- 图片 artifact 注册。

当前 capabilities 已明确标记：

```text
logo.image_generate = false
```

### 6.5 Phase 9 Online API Documentation 未完成项

已完成：

- 已实现接口有 summary。
- 已实现接口有 description。
- 已实现接口大多有 response_model。
- OpenAPI 已包含 v1 基础路由。

未完成：

- 统一错误响应模型未系统挂到每个接口。
- reports/artifacts/ai-logo 的 OpenAPI 不存在。
- 对外请求/响应样例还不完整。
- Header 鉴权说明未内置到 OpenAPI security scheme。

### 6.6 Phase 10 Final Verification / Deployment 未完成

未完成：

- 未跑完整后端回归测试。
- 未启动真实 Gateway 做 Swagger 验证。
- 未完成远端 dev 环境部署。
- 未形成非容器化部署脚本。
- 未完成接口 smoke test。

特别说明：

本地尝试启动 Gateway 时，因缺少 `config.yaml` 启动失败。这不是 v1 代码测试失败，而是运行环境配置缺失。后续部署前必须先处理 dev 环境配置。

## 7. 当前风险清单

### R1 数据源还没有进入模型上下文闭环

严重度：高  
影响：前端传了 `datasource_ids`，后端也解析了，但如果 agent 不读取 `selected_data_sources`，模型可能无法真正基于数据源回答。

建议：

1. 在 agent middleware 层读取 `runtime.context["selected_data_sources"]`。
2. 构造成受控 system/context message。
3. 保持用户原始 `content` 不变。
4. 添加测试验证最终 agent input 中包含 selected source context。

### R2 API Key 只是存在性校验

严重度：高  
影响：外部接口虽然要求 `X-API-Key`，但没有真实密钥验证，不适合直接暴露到公网或多团队共享环境。

建议：

1. 增加 app/api key 配置表或配置文件。
2. 支持 key hash 存储。
3. 支持 app 级启停、过期、权限范围。
4. OpenAPI 增加 security scheme。

### R3 数据源存储在 thread metadata 中，不适合大内容

严重度：中高  
影响：长文本、文件内容、URL 抓取内容直接进 metadata 会导致存储膨胀和查询性能问题。

建议：

1. metadata 只保存数据源索引信息。
2. 原文保存到文件、对象存储或数据库表。
3. 大文本分块并建立检索索引。

### R4 Artifact 没有 v1 稳定 ID

严重度：中高  
影响：报告和 Logo 都依赖产物下载。如果没有 Artifact Registry，外部团队会被迫感知内部 path。

建议：

1. 优先做 Phase 7。
2. 报告和 Logo 统一返回 artifact_id。

### R5 Agent invoke 使用临时 conversation_id

严重度：中  
影响：`POST /api/v1/agents/{agent_id}/invoke` 当前生成临时 conversation_id。如果底层 run 创建要求 thread 已存在，后续真实集成可能暴露问题。

建议：

1. invoke 前显式创建临时 conversation/thread。
2. 或要求调用方必须传 conversation_id。
3. 增加真实 run 集成测试。

## 8. 建议后续执行顺序

### Step 1 补齐 Phase 5 数据源注入闭环

目标：

- 确保 `selected_data_sources` 真实进入模型上下文。
- 保持 `content` 原样。
- 支持 citation_required 的基本输出约束。

建议新增：

```text
backend/packages/harness/deerflow/agents/middlewares/selected_data_sources_middleware.py
backend/tests/test_v1_data_source_context_injection.py
```

### Step 2 实现 Phase 7 Artifact Registry

目标：

- 先建立稳定 `artifact_id`。
- 为报告和 Logo 铺路。

建议接口：

```text
GET /api/v1/artifacts/{artifact_id}
GET /api/v1/conversations/{conversation_id}/artifacts
```

### Step 3 实现 Phase 6 报告生成

目标：

- 根据用户输入、对话历史、数据源生成报告。
- 支持 DOCX/PDF。
- 返回 artifact_id。

建议接口：

```text
POST /api/v1/conversations/{conversation_id}/reports
GET  /api/v1/reports/{report_id}
```

### Step 4 实现 Phase 8 AI Logo

目标：

- 根据语义生成 Logo 设计规格。
- 调用图片生成能力。
- 保存图片并注册 artifact。

建议接口：

```text
POST /api/v1/ai/logo/generate
GET  /api/v1/ai/logo/jobs/{job_id}
```

### Step 5 完成 Phase 9/10

目标：

- 完整 OpenAPI。
- 统一错误模型。
- 远端 dev 非容器化部署脚本。
- Swagger 远端验证。
- smoke test。

## 9. 交接给前端团队的当前接口说明

当前前端可先联调：

```text
POST /api/v1/conversations
POST /api/v1/conversations/{conversation_id}/data-sources
POST /api/v1/conversations/{conversation_id}/messages
POST /api/v1/conversations/{conversation_id}/stream
GET  /api/v1/conversations
GET  /api/v1/conversations/{conversation_id}/messages
GET  /api/v1/agents
GET  /api/v1/runs/{run_id}
POST /api/v1/runs/{run_id}/cancel
GET  /api/v1/capabilities
```

统一 Header：

```text
X-App-Id: frontend-app
X-API-Key: dev-key
X-User-Id: user-001
X-Request-Id: req-001
```

对话 + 数据源联调流程：

1. 创建会话：`POST /api/v1/conversations`
2. 注册数据源：`POST /api/v1/conversations/{conversation_id}/data-sources`
3. 拿到 `datasource_id`
4. 对话发送时传 `datasource_ids`
5. 前端不要把数据源正文拼入 `content`

## 10. 代码变更状态

当前工作区包含新增 v1 后端文件、测试文件、执行计划文档更新。

注意：

- `.deploy.conf` 和 `AGENTS.md` 是工作区中已有未跟踪文件，不属于本次 v1 能力实现核心范围。
- 当前 v1 实现尚未提交到 Git。
- 远端 dev 环境尚未部署。

## 11. 验收建议

在交给下一位成员继续开发前，建议先执行：

```bash
cd backend
python -m pytest tests/test_v1_external_context.py tests/test_v1_run_adapter.py tests/test_v1_sse_mapper.py tests/test_v1_capabilities.py tests/test_v1_conversations.py tests/test_v1_agents.py tests/test_v1_runs.py tests/test_v1_data_sources.py tests/test_v1_openapi.py -q
python -m ruff check app/gateway/services.py app/gateway/schemas/v1 app/gateway/routers/v1 app/gateway/v1_services tests/test_v1_*.py
```

预期：

```text
14 passed
All checks passed
```

