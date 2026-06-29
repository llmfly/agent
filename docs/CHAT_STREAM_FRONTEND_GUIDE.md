# Intelli Engine 对话 Stream 前端接入与渲染文档

版本: v0.1
日期: 2026-06-24
适用对象: 对接 Intelli Engine 对话接口的前端工程师。

本文说明前端应该使用哪个 stream 接口、每个 SSE event 的含义、`data` 字段结构，以及如何区分并渲染模型正文、思考过程、检索过程、工具调用、工具结果、错误和最终消息快照。

## 1. 接口选择结论

前端如果要完整渲染聊天过程，推荐使用底层 LangGraph 兼容接口:

```http
POST /api/threads/{thread_id}/runs/stream
```

不建议用下面这个接口做完整聊天渲染:

```http
POST /api/v1/conversations/{conversation_id}/stream
```

原因是 `/api/v1/conversations/{conversation_id}/stream` 当前是简化流，会把底层 rich events 映射成少量 v1 事件，只保留文本 delta。类似 `additional_kwargs.reasoning_content`、`tool_calls`、工具结果、检索过程等信息不会完整保留。

| 接口 | 适合场景 | 是否包含思考/工具/检索细节 |
|---|---|---|
| `/api/threads/{thread_id}/runs/stream` | Web 前端完整聊天 UI | 是 |
| `/api/v1/conversations/{conversation_id}/stream` | 外部系统只需要简单文本流 | 否 |

v1 conversation stream 当前只会输出这些简化事件:

| event | data | 说明 |
|---|---|---|
| `run.started` | `{ run_id, conversation_id, agent_id }` | 运行开始 |
| `message.delta` | `{ conversation_id, agent_id, delta }` | 正文文本增量 |
| `run.failed` | `{ conversation_id, error }` | 运行失败 |
| `run.completed` | `{ conversation_id, status }` | 运行完成 |

所以，前端要区分“思考过程 / 最终内容 / 正在搜索 / 工具调用 / 工具结果”，请接 `/api/threads/{thread_id}/runs/stream`。

## 2. 推荐请求格式

```http
POST /api/threads/thread_001/runs/stream
Content-Type: application/json
Accept: text/event-stream
X-App-Id: notebook-app
X-API-Key: dev-key
X-User-Id: smoke-user
X-Request-Id: chat-stream-001
```

```json
{
  "assistant_id": "default",
  "input": {
    "messages": [
      {
        "role": "user",
        "content": "请帮我分析这份材料，并给出结论。"
      }
    ]
  },
  "stream_mode": ["values", "messages"],
  "context": {
    "thinking_enabled": true
  },
  "on_disconnect": "continue"
}
```

请求字段说明:

| 字段 | 类型 | 必填 | 说明 |
|---|---:|---:|---|
| `assistant_id` | string/null | 否 | Agent/assistant ID。不传时使用默认 agent。 |
| `input.messages` | array | 是 | 本轮用户输入消息。 |
| `stream_mode` | string/array | 建议传 | 聊天 UI 推荐 `['values', 'messages']`。 |
| `context.thinking_enabled` | boolean | 否 | 是否启用模型思考能力，模型本身也需要支持。 |
| `context.model_name` | string | 否 | 指定模型。 |
| `context.reasoning_effort` | string | 否 | reasoning 强度，取决于模型和配置。 |
| `on_disconnect` | string | 否 | 推荐 `continue`，前端断开后后端继续执行。 |

`stream_mode` 说明:

| stream_mode | SSE event | 说明 | 前端是否推荐 |
|---|---|---|---|
| `messages` | `messages` | 消息增量，包含正文、思考、工具调用、工具结果。 | 推荐 |
| `values` | `values` | 完整状态快照，通常包含完整 `messages` 列表。 | 推荐 |
| `updates` | `updates` | LangGraph 节点级更新。 | 调试可用 |
| `custom` | `custom` | 自定义事件。 | 按业务需要 |
| `checkpoints` | `checkpoints` | checkpoint 事件。 | 一般不用 |
| `tasks` | `tasks` | task/debug 事件。 | 一般不用 |
| `debug` | `debug` | debug 事件。 | 一般不用 |
| `events` | 不支持 | 当前 Gateway 不支持该 mode。 | 不要使用 |

## 3. SSE 外层协议

服务端返回标准 SSE:

```text
event: messages
data: [{"type":"ai","content":"你好","id":"msg_1"},{}]
id: 12
```

外层字段说明:

| 字段 | 类型 | 说明 |
|---|---:|---|
| `event` | string | 事件名，例如 `metadata`、`messages`、`values`、`error`、`end`。 |
| `data` | JSON | 当前事件的数据。不同 event 的结构不同。 |
| `id` | string | 递增事件 ID，可用于 `Last-Event-ID` 断线续传。 |
| `: heartbeat` | SSE comment | 心跳注释，不是业务事件，前端忽略即可。 |

## 4. Event 完整说明

### 4.1 `metadata`

运行开始时发送。

```text
event: metadata
data: {"run_id":"run_xxx","thread_id":"thread_xxx"}
id: 1
```

| 字段 | 类型 | 说明 |
|---|---:|---|
| `run_id` | string | 本次运行 ID。取消、join、查消息、查事件都需要它。 |
| `thread_id` | string | 当前 thread/conversation ID。 |

前端处理:

- 保存 `run_id`。
- 当前 run 状态置为 running。
- UI 开始显示“生成中”。

### 4.2 `messages`

最重要的事件。模型正文增量、思考过程、工具调用、检索过程、工具结果都看它。

```text
event: messages
data: [messageChunk, metadata]
id: 2
```

`data` 是长度为 2 的数组:

| 位置 | 名称 | 说明 |
|---:|---|---|
| `data[0]` | `messageChunk` | 消息增量或工具消息。 |
| `data[1]` | `metadata` | LangGraph metadata，例如节点名、checkpoint 信息等。 |

`messageChunk` 通用字段:

| 字段 | 类型 | 说明 |
|---|---:|---|
| `type` | string | 消息类型，常见值为 `ai`、`human`、`tool`、`system`。 |
| `id` | string/null | 消息 ID。同一个 `id` 的 chunk 应该合并。 |
| `content` | string/array | AI 正文、tool 结果内容，或 content blocks。 |
| `additional_kwargs` | object | 扩展字段。思考过程和 token 归因主要看这里。 |
| `tool_calls` | array | AI 发起的工具调用。 |
| `name` | string/null | 工具名或消息名。 |
| `tool_call_id` | string/null | `type: 'tool'` 时，关联到前面 `tool_calls[].id`。 |
| `usage_metadata` | object | token 使用信息。 |
| `response_metadata` | object | 模型响应元信息，例如 finish reason。 |

### 4.3 `values`

完整状态快照。

```text
event: values
data: {"messages":[...]}
id: 8
```

常见字段:

| 字段 | 类型 | 说明 |
|---|---:|---|
| `messages` | array | 当前完整消息列表。 |
| `title` | string/null | 会话标题，如果状态里有。 |
| `artifacts` | array | 产物列表，如果状态里有。 |

前端处理:

- 用 `values.messages` 作为最终或阶段性状态校准。
- 如果前端对 `messages` 增量合并有遗漏，以最新 `values.messages` 为准。

### 4.4 `error`

运行异常时发送。

```text
event: error
data: {"message":"Run failed","name":"RuntimeError"}
id: 20
```

| 字段 | 类型 | 说明 |
|---|---:|---|
| `message` | string | 错误描述。 |
| `name` | string | 错误类型。 |

前端处理:

- 当前 run 状态置为 failed。
- 展示 `message`。
- 停止 loading。

### 4.5 `end`

流结束。

```text
event: end
data: null
id: 21
```

前端处理:

- 停止 loading。
- 如果之前没有收到 `error`，当前 run 状态置为 completed。
- 可选: 重新拉取历史消息做最终校准。

## 5. 如何区分思考过程和正文

按下面优先级判断。

### 5.1 优先看 `additional_kwargs.reasoning_content`

这是当前最明确的思考过程字段。

```json
{
  "type": "ai",
  "id": "msg_1",
  "content": "",
  "additional_kwargs": {
    "reasoning_content": "我需要先判断用户要的是接口文档，而不是继续口头解释。"
  }
}
```

渲染规则:

- 渲染到“思考过程 / Thinking”区域。
- 不要拼进最终回答正文。
- 同一个 `id` 的多次 reasoning chunk 需要合并。
- 收到 `values.messages` 后，用完整状态校准。

### 5.2 兼容 `content` 数组里的 thinking block

部分模型或网关会把 thinking 放在 content blocks 里。

```json
{
  "type": "ai",
  "id": "msg_1",
  "content": [
    {
      "type": "thinking",
      "thinking": "先检索资料，再组织答案。"
    },
    {
      "type": "text",
      "text": "结论如下..."
    }
  ]
}
```

渲染规则:

- `type === 'thinking'` 或存在 `thinking` 字段的 block，渲染为思考过程。
- `type === 'text'` 或存在 `text` 字段的 block，渲染为正文。

### 5.3 兼容 `<think>...</think>` 内联格式

兜底兼容:

```json
{
  "type": "ai",
  "id": "msg_1",
  "content": "<think>先分析问题</think>最终回答"
}
```

渲染规则:

- `<think>...</think>` 内部是思考过程。
- 标签外是正文。

### 5.4 普通正文

如果没有以上思考字段，则 `content` 是普通正文。

```json
{
  "type": "ai",
  "id": "msg_1",
  "content": "这是最终回答。"
}
```

## 6. 如何区分工具调用、检索过程和工具结果

### 6.1 AI 发起工具调用

当 `messageChunk.type === 'ai'` 且 `tool_calls` 非空，表示模型准备调用工具。

```json
{
  "type": "ai",
  "id": "msg_2",
  "content": "",
  "tool_calls": [
    {
      "id": "call_abc",
      "name": "web_search",
      "args": {
        "query": "Intelli Engine stream event"
      }
    }
  ]
}
```

`tool_calls[]` 字段:

| 字段 | 类型 | 说明 |
|---|---:|---|
| `id` | string | 工具调用 ID。 |
| `name` | string | 工具名。 |
| `args` | object | 工具参数。 |

### 6.2 常见工具名和展示建议

| 工具名 | 含义 | 前端展示建议 |
|---|---|---|
| `web_search` | 网页搜索 | `正在搜索: {args.query}` |
| `image_search` | 图片搜索 | `正在搜索图片: {args.query}` |
| `web_fetch` | 抓取/查看网页 | `正在查看网页` |
| `present_files` | 展示生成文件 | `正在整理文件` |
| `write_todos` | 更新任务列表 | `正在更新任务列表` |
| `task` | 派发子任务/subagent | 优先展示 `args.description` |
| 其他工具 | 普通工具调用 | `正在使用工具: {name}` |

当前没有单独的 `search.started` event。检索过程通过工具名判断:

```ts
const isSearchTool =
  toolCall.name === "web_search" ||
  toolCall.name === "image_search" ||
  toolCall.name === "web_fetch";
```

### 6.3 工具结果

工具执行结果通常是 `type: 'tool'` 的消息。

```json
{
  "type": "tool",
  "id": "tool_msg_1",
  "name": "web_search",
  "tool_call_id": "call_abc",
  "content": "搜索结果内容..."
}
```

字段说明:

| 字段 | 类型 | 说明 |
|---|---:|---|
| `type` | string | 固定为 `tool`。 |
| `name` | string/null | 工具名。 |
| `tool_call_id` | string | 对应前面 `tool_calls[].id`。 |
| `content` | string | 工具返回内容。 |
| `id` | string/null | 工具结果消息 ID。 |

前端处理:

- 用 `tool_call_id` 找到之前的 `tool_calls[].id`。
- 将该工具调用状态从 running 改成 completed。
- 工具结果是否展示给用户由产品决定；搜索结果通常建议折叠展示。

## 7. `additional_kwargs` 重点字段

| 字段 | 类型 | 说明 | 前端处理 |
|---|---:|---|---|
| `reasoning_content` | string/null | 模型思考过程。 | 渲染到思考区域。 |
| `hide_from_ui` | boolean | 是否隐藏该消息。 | 为 `true` 时不展示。 |
| `files` | array/object | 上传文件或关联文件元数据。 | 展示附件。 |
| `token_usage_attribution` | object | token 归因。 | 用于 token/步骤统计。 |
| `deerflow_error_fallback` | boolean | LLM fallback 错误标记。 | 用于错误处理。 |
| `error_detail` | string | fallback 错误详情。 | 错误展示或调试。 |
| `error_reason` | string | fallback 错误原因。 | 错误展示或调试。 |

### 7.1 `token_usage_attribution`

示例:

```json
{
  "additional_kwargs": {
    "token_usage_attribution": {
      "version": 1,
      "kind": "thinking",
      "shared_attribution": false,
      "tool_call_ids": ["call_abc"],
      "actions": [
        {
          "kind": "tool",
          "tool_name": "web_search",
          "tool_call_id": "call_abc"
        }
      ]
    }
  }
}
```

字段说明:

| 字段 | 类型 | 说明 |
|---|---:|---|
| `version` | number | 归因格式版本。 |
| `kind` | string | 高层归因类型。 |
| `shared_attribution` | boolean | 是否多个动作共享 token。 |
| `tool_call_ids` | string[] | 关联的工具调用 ID。 |
| `actions` | array | 更细粒度的动作列表。 |

`kind` 常见值:

| kind | 含义 |
|---|---|
| `thinking` | 思考过程。 |
| `final_answer` | 最终回答。 |
| `tool_batch` | 工具调用批次。 |
| `todo_update` | 任务列表更新。 |
| `subagent_dispatch` | 子任务派发。 |

`actions[].kind` 常见值:

| action kind | 含义 |
|---|---|
| `search` | 搜索。 |
| `tool` | 工具调用。 |
| `subagent` | 子任务。 |
| `present_files` | 文件展示。 |
| `clarification` | 澄清问题。 |

## 8. 前端消息合并策略

`messages` 是增量事件，同一个 AI 消息可能分多次返回。前端应按 `message.id` 合并。

推荐策略:

1. 如果没有 `id`，创建临时消息。
2. 如果已有相同 `id`，合并到已有消息。
3. `content` 为字符串正文时追加。
4. `additional_kwargs.reasoning_content` 存在时合并到 thinking 字段。
5. `tool_calls` 存在时按 `tool_calls[].id` 去重合并。
6. `type === 'tool'` 时按 `tool_call_id` 关联到工具调用。
7. 收到 `values.messages` 后，用完整消息列表校准本地状态。

## 9. 推荐 TypeScript 类型

```ts
type StreamEventName =
  | "metadata"
  | "messages"
  | "values"
  | "updates"
  | "custom"
  | "checkpoints"
  | "tasks"
  | "debug"
  | "error"
  | "end";

interface SseEvent<T = unknown> {
  event: StreamEventName;
  data: T;
  id?: string;
}

interface ToolCall {
  id?: string;
  name: string;
  args: Record<string, unknown>;
}

interface TokenUsageAttribution {
  version?: number;
  kind?:
    | "thinking"
    | "final_answer"
    | "tool_batch"
    | "todo_update"
    | "subagent_dispatch";
  shared_attribution?: boolean;
  tool_call_ids?: string[];
  actions?: Array<{
    kind?: string;
    tool_name?: string | null;
    description?: string | null;
    tool_call_id?: string;
  }>;
}

interface ChatMessage {
  type: "ai" | "human" | "tool" | "system" | string;
  id?: string | null;
  content?: string | Array<Record<string, unknown>>;
  additional_kwargs?: {
    reasoning_content?: string | null;
    hide_from_ui?: boolean;
    files?: unknown;
    token_usage_attribution?: TokenUsageAttribution;
    [key: string]: unknown;
  };
  tool_calls?: ToolCall[];
  name?: string | null;
  tool_call_id?: string | null;
  usage_metadata?: Record<string, unknown>;
  response_metadata?: Record<string, unknown>;
}

type MessagesEventData = [ChatMessage, Record<string, unknown>];

interface ValuesEventData {
  messages?: ChatMessage[];
  title?: string | null;
  artifacts?: unknown[];
  [key: string]: unknown;
}
```

## 10. 推荐渲染辅助函数

```ts
function getReasoningText(message: ChatMessage): string | null {
  if (message.type !== "ai") return null;

  const reasoning = message.additional_kwargs?.reasoning_content;
  if (typeof reasoning === "string" && reasoning.length > 0) {
    return reasoning;
  }

  if (Array.isArray(message.content)) {
    const thinkingBlocks = message.content
      .map((part) => {
        if (part.type === "thinking" && typeof part.thinking === "string") {
          return part.thinking;
        }
        if (typeof part.thinking === "string") {
          return part.thinking;
        }
        return "";
      })
      .filter(Boolean);
    return thinkingBlocks.length ? thinkingBlocks.join("\n") : null;
  }

  if (typeof message.content === "string") {
    const match = message.content.match(/<think>([\s\S]*?)<\/think>/);
    return match?.[1] ?? null;
  }

  return null;
}

function getAnswerText(message: ChatMessage): string {
  if (typeof message.content !== "string") return "";
  return message.content.replace(/<think>[\s\S]*?<\/think>/g, "").trim();
}

function isToolCallingMessage(message: ChatMessage): boolean {
  return message.type === "ai" && !!message.tool_calls?.length;
}

function isToolResultMessage(message: ChatMessage): boolean {
  return message.type === "tool";
}

function isHiddenMessage(message: ChatMessage): boolean {
  return message.additional_kwargs?.hide_from_ui === true;
}
```

## 11. UI 状态机建议

| 输入事件 | 条件 | UI 行为 |
|---|---|---|
| `metadata` | always | 记录 `run_id`，状态置为 running。 |
| `messages` | `ai + reasoning_content` | 更新思考面板。 |
| `messages` | `ai + content` | 追加回答正文。 |
| `messages` | `ai + tool_calls` | 展示工具调用/搜索中。 |
| `messages` | `tool` | 关联工具结果，工具状态置为 completed。 |
| `values` | `messages` 存在 | 用完整消息快照校准。 |
| `error` | always | 展示错误，状态置为 failed。 |
| `end` | always | 停止 loading，状态置为 completed。 |

## 12. 完整流式示例

### 12.1 运行开始

```text
event: metadata
data: {"run_id":"run_001","thread_id":"thread_001"}
id: 1
```

### 12.2 思考过程

```text
event: messages
data: [{"type":"ai","id":"msg_ai_1","content":"","additional_kwargs":{"reasoning_content":"我需要先检索相关信息。"}},{"langgraph_node":"agent"}]
id: 2
```

前端展示:

```text
思考中: 我需要先检索相关信息。
```

### 12.3 发起搜索

```text
event: messages
data: [{"type":"ai","id":"msg_ai_1","content":"","tool_calls":[{"id":"call_search_1","name":"web_search","args":{"query":"Intelli Engine stream event"}}]},{"langgraph_node":"agent"}]
id: 3
```

前端展示:

```text
正在搜索: Intelli Engine stream event
```

### 12.4 搜索结果

```text
event: messages
data: [{"type":"tool","id":"tool_msg_1","name":"web_search","tool_call_id":"call_search_1","content":"搜索结果内容..."},{"langgraph_node":"tools"}]
id: 4
```

前端处理:

- 将 `call_search_1` 对应的搜索状态置为 completed。
- 结果可折叠展示。

### 12.5 回答正文

```text
event: messages
data: [{"type":"ai","id":"msg_ai_2","content":"根据检索结果，结论如下: "},{"langgraph_node":"agent"}]
id: 5
```

```text
event: messages
data: [{"type":"ai","id":"msg_ai_2","content":"第一，... 第二，..."},{"langgraph_node":"agent"}]
id: 6
```

前端处理:

- 同一个 `msg_ai_2` 的 `content` 追加为完整回答。

### 12.6 完整状态校准

```text
event: values
data: {"messages":[{"type":"human","content":"请帮我分析","id":"msg_user_1"},{"type":"ai","content":"根据检索结果，结论如下: 第一，... 第二，...","id":"msg_ai_2"}]}
id: 7
```

前端处理:

- 用 `values.messages` 覆盖或校准本地消息列表。

### 12.7 流结束

```text
event: end
data: null
id: 8
```

前端处理:

- 停止 loading。
- run 状态置为 completed。

## 13. 历史消息和调试接口

重新加载 thread 消息:

```http
GET /api/threads/{thread_id}/messages?limit=50
```

查询某个 run 的消息:

```http
GET /api/threads/{thread_id}/runs/{run_id}/messages?limit=50
```

查询某个 run 的完整事件，用于调试:

```http
GET /api/threads/{thread_id}/runs/{run_id}/events?limit=500
```

## 14. 最小可用处理逻辑

```ts
function handleStreamEvent(event: SseEvent) {
  switch (event.event) {
    case "metadata": {
      const data = event.data as { run_id: string; thread_id: string };
      setRunId(data.run_id);
      setRunning(true);
      return;
    }

    case "messages": {
      const [message] = event.data as MessagesEventData;
      if (!message || isHiddenMessage(message)) return;

      const reasoning = getReasoningText(message);
      if (reasoning) {
        mergeReasoning(message.id, reasoning);
        return;
      }

      if (isToolCallingMessage(message)) {
        mergeToolCalls(message.id, message.tool_calls ?? []);
        return;
      }

      if (isToolResultMessage(message)) {
        mergeToolResult(message.tool_call_id, message.name, message.content);
        return;
      }

      if (message.type === "ai") {
        const answer = getAnswerText(message);
        if (answer) appendAnswerDelta(message.id, answer);
      }
      return;
    }

    case "values": {
      const data = event.data as ValuesEventData;
      if (Array.isArray(data.messages)) {
        replaceMessagesFromSnapshot(data.messages);
      }
      return;
    }

    case "error": {
      const data = event.data as { message?: string; name?: string };
      setError(data.message ?? "Run failed");
      setRunning(false);
      return;
    }

    case "end": {
      setRunning(false);
      return;
    }
  }
}
```

## 15. 前端验收清单

- 能识别 `metadata` 并保存 `run_id`。
- 能从 `messages` 中渲染 AI 正文增量。
- 能从 `additional_kwargs.reasoning_content` 渲染思考过程。
- 能兼容 content block 里的 `thinking`。
- 能兼容 `<think>...</think>` 内联格式。
- 能识别 `tool_calls` 并展示工具调用中。
- 能通过 `web_search`、`image_search`、`web_fetch` 展示检索过程。
- 能通过 `tool_call_id` 把工具结果关联回工具调用。
- 能忽略 `additional_kwargs.hide_from_ui === true` 的消息。
- 能用 `values.messages` 校准最终消息列表。
- 能处理 `error` 和 `end`。
- 能在断线重连时使用 SSE `id` / `Last-Event-ID`，或重新拉取历史消息校准。
