# Intelli Engine v1 对话接口文档

所有接口前缀为 `/api/v1`，通过 nginx 反向代理暴露。`conversation_id` 内部映射为 `thread_id`，对外统一使用 `conversation_id`。

---

## 1. 流式对话接口

### `POST /api/v1/conversations/{conversation_id}/stream`

发送一条消息并接收 SSE 流式响应。

**请求体：**

```json
{
  "message": "用户消息内容",
  "run_id": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message` | string | 是 | 用户消息内容 |
| `run_id` | string \| null | 否 | 指定运行 ID，不传则自动生成 |

**响应：** SSE (Server-Sent Events)

| event | data | 说明 |
|-------|------|------|
| `run.started` | `{"run_id":"...","conversation_id":"..."}` | 运行开始 |
| `message.delta` | `{"delta":"文本片段"}` | 模型回复文本增量 |
| `thinking.delta` | `{"delta":"思考过程片段"}` | 模型思考过程增量 |
| `tool_call` | `{"name":"tool_name","arguments":{...}}` | 工具调用 |
| `tool.result` | `{"name":"tool_name","result":"..."}` | 工具执行结果 |
| `panel.patch` | `{"todo":[...],"artifacts":[...]}` | 侧边栏（产物/待办）更新 |
| `run.completed` | `{"run_id":"..."}` | 运行成功完成 |
| `run.failed` | `{"run_id":"...","error":"错误描述"}` | 运行失败 |

---

## 2. 对话状态接口

### `GET /api/v1/conversations/{conversation_id}/state`

获取当前对话的完整状态，包含产物列表和元数据。

**响应：**

```json
{
  "thread_id": "conv_xxx",
  "values": {
    "artifacts": [
      "/mnt/user-data/outputs/poem.md",
      "/data/intelli/engine/.deer-flow/users/.../reports/report.docx"
    ],
    "messages": [...]
  },
  "metadata": {
    "title": "对话标题"
  }
}
```

> `state.artifacts` 合并了 `present_files` 产物（路径格式）和 report_workflow 产物（DB 持久化路径）。

### `PATCH /api/v1/conversations/{conversation_id}/state`

更新会话状态元数据。

**请求体：**

```json
{
  "metadata": {"key": "value"}
}
```

---

## 3. 历史对话接口

### `GET /api/v1/conversations/{conversation_id}/messages`

获取对话的完整消息历史。

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `limit` | int | 否 | 返回条数限制，默认 50 |
| `before` | string | 否 | 分页游标，上一页最后一条消息的 ID |

**响应：**

```json
{
  "messages": [
    {
      "role": "user",
      "content": "...",
      "id": "msg_xxx",
      "created_at": "2026-06-26T10:00:00Z"
    },
    {
      "role": "assistant",
      "content": "...",
      "tool_calls": [
        {"name": "generate_report", "arguments": {}}
      ],
      "token_usage": {"input": 100, "output": 50}
    }
  ],
  "pagination": {"next_cursor": "msg_yyy"}
}
```

---

## 4. 产物查询接口

### `GET /api/v1/conversations/{conversation_id}/artifacts`

获取会话中所有产物（报告、文件、图片等）。

**响应：**

```json
[
  {
    "artifact_id": "path:/data/.../report.docx",
    "conversation_id": "conv_xxx",
    "filename": "report_20260626_144810.docx",
    "url": "/api/v1/artifacts/art_file_xxx",
    "created_at": "2026-06-26T14:48:10Z",
    "metadata": {
      "source": "artifact_service",
      "path": "/data/intelli/engine/.deer-flow/users/.../report.docx",
      "download_url": "/api/v1/artifacts/art_file_xxx?download=true"
    }
  }
]
```

### `GET /api/v1/artifacts/{artifact_id}`

获取产物元数据。

### `GET /api/v1/artifacts/{artifact_id}/download`

强制下载产物文件。支持 `?download=true` 参数等价。

### `GET /api/v1/artifacts/{artifact_id}/preview`

在线预览产物（文本内容直接返回，HTML 可渲染）。
