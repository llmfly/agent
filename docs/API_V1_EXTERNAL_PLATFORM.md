# intelli-engine v1 外部 API 接口文档

> 版本: v0.1  
> 基准 URL: `http://localhost:8081`  
> 接口前缀: `/api/v1/`

---

## 目录

- [1. 能力发现](#1-能力发现)
- [2. Agent 清单](#2-agent-清单)
- [3. 数据源管理](#3-数据源管理)
  - [3.1 注册数据源](#31-注册数据源)
  - [3.2 查询数据源列表](#32-查询数据源列表)
  - [3.3 查询单个数据源](#33-查询单个数据源)
  - [3.4 自然语言查询数据源](#34-自然语言查询数据源)
- [4. 报告生成](#4-报告生成)
  - [4.1 创建报告生成任务](#41-创建报告生成任务)
  - [4.2 查询报告状态](#42-查询报告状态)
- [5. Artifact 下载](#5-artifact-下载)
- [6. 数据源配置参考](#6-数据源配置参考)
  - [6.1 SQL 数据源](#61-sql-数据源)
  - [6.2 Elasticsearch 数据源](#62-elasticsearch-数据源)

---

## 1. 能力发现

查询当前 intelli-engine 实例支持的所有能力，外部应用可用此接口做功能自适应。

```http
GET /api/v1/capabilities
```

### 响应示例

```json
{
  "conversation": {
    "supported": true,
    "streaming": true,
    "multi_turn": true,
    "file_upload": true
  },
  "agents": {
    "supported": true,
    "custom_agents": true,
    "subagents": true,
    "available": [
      { "agent_id": "lead-agent", "name": "通用智能体", "type": "system", "description": "通用任务和对话" }
    ]
  },
  "data_sources": {
    "supported": true,
    "types": ["text", "file", "url", "sql", "es"],
    "nl_query": {
      "supported": true,
      "text_to_sql": {
        "supported": true,
        "dialects": ["mysql", "postgresql", "sqlite", "mssql", "oracle"],
        "description": "自然语言转 SQL 并自动执行查询"
      },
      "text_to_es": {
        "supported": true,
        "description": "自然语言转 Elasticsearch Query DSL 并自动执行查询"
      }
    }
  },
  "reports": {
    "supported": true,
    "formats": ["docx", "html"],
    "types": ["analysis", "summary", "research", "meeting_notes", "decision_memo"],
    "max_datasources": 20,
    "features": [
      "基于数据源自动生成报告",
      "Text-to-SQL 数据查询集成",
      "Text-to-ES 数据查询集成",
      "多格式导出 (DOCX/HTML)"
    ]
  }
}
```

---

## 2. Agent 清单

查询可用的智能体列表。

```http
GET /api/v1/agents
```

### 响应示例

```json
{
  "agents": [
    {
      "agent_id": "lead-agent",
      "name": "通用智能体",
      "type": "system",
      "description": "通用任务和对话",
      "enabled": true
    }
  ]
}
```

---

## 3. 数据源管理

### 3.1 注册数据源

注册一个数据源到指定会话（conversation）。数据源类型支持：`text`（文本）、`file`（文件）、`url`（链接）、`sql`（数据库）、`es`（Elasticsearch）。

```http
POST /api/v1/conversations/{conversation_id}/data-sources
```

#### 路径参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `conversation_id` | string | 会话 ID |

#### 请求体

```json
{
  "type": "sql",
  "name": "学生成绩数据库",
  "content": null,
  "url": null,
  "file_id": null,
  "metadata": {
    "db_type": "mysql",
    "host": "172.16.0.164",
    "port": 3306,
    "database": "student",
    "username": "root",
    "password": "root@2024."
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 数据源类型: `text`, `file`, `url`, `sql`, `es` |
| `name` | string | 是 | 数据源名称 |
| `content` | string | 否 | type=text 时传入文本内容 |
| `url` | string | 否 | type=url 时传入 URL |
| `file_id` | string | 否 | type=file 时传入已上传文件 ID |
| `metadata` | object | 否 | 连接参数（SQL/ES 类型必填） |

#### 响应示例

```json
{
  "datasource_id": "ds_093c5ff90c54",
  "conversation_id": "conv001",
  "type": "sql",
  "name": "学生成绩数据库",
  "content_preview": "[SQL Database] type=mysql, host=172.16.0.164, database=student",
  "status": "ready",
  "created_at": "2026-06-23T10:00:00",
  "metadata": {
    "db_type": "mysql",
    "host": "172.16.0.164",
    "port": 3306,
    "database": "student"
  }
}
```

#### SQL 数据源的 metadata 说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `db_type` | string | 是 | - | `mysql`, `postgresql`, `sqlite`, `mssql`, `oracle` |
| `host` | string | 是 | `localhost` | 数据库主机地址 |
| `port` | int | 是 | `3306` | 数据库端口 |
| `database` | string | 是 | - | 数据库名 |
| `username` | string | 是 | - | 数据库用户名 |
| `password` | string | 是 | - | 数据库密码（含特殊字符自动编码） |

> **注意**: 表结构由系统在执行查询时自动发现（SHOW TABLES + SHOW FULL COLUMNS + 外键检测），无需手动提供。自动发现结果包含每张表的字段名、类型、主键/外键、注释及行数，系统会根据查询意图自动检索相关表。

#### ES 数据源的 metadata 说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `hosts` | string[] | 是 | `["http://localhost:9200"]` | ES 节点地址列表 |
| `index` | string | 是 | - | 默认查询索引 |
| `username` | string | 否 | - | 认证用户名 |
| `password` | string | 否 | - | 认证密码 |

---

### 3.2 查询数据源列表

查询某个会话下的所有数据源。

```http
GET /api/v1/conversations/{conversation_id}/data-sources
```

#### 响应示例

```json
{
  "datasources": [
    {
      "datasource_id": "ds_093c5ff90c54",
      "conversation_id": "conv001",
      "type": "sql",
      "name": "学生成绩数据库",
      "content_preview": "[SQL Database] type=mysql...",
      "status": "ready",
      "created_at": "2026-06-23T10:00:00",
      "metadata": {}
    }
  ],
  "total": 1
}
```

---

### 3.3 查询单个数据源

```http
GET /api/v1/conversations/{conversation_id}/data-sources/{datasource_id}
```

#### 响应: 同 3.2 的单个 DataSourceResponse

---

### 3.4 自然语言查询数据源

用自然语言对数据源进行查询。**这是整个核心能力接口**。

对于 **SQL** 数据源：自动发现 Schema → 生成 SQL → 执行 → 返回结构化结果  
对于 **ES** 数据源：自然语言 → ES Query DSL → 执行 → 返回结构化结果  
对于 **text/file/url** 数据源：返回存储的原始内容

```http
POST /api/v1/conversations/{conversation_id}/data-sources/{datasource_id}/query
```

#### 请求体

```json
{
  "query": "统计2024级各专业的学生人数",
  "max_results": 10
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `query` | string | 是 | - | 自然语言查询描述 |
| `max_results` | int | 否 | 50 | 最大返回行数 (1-1000) |

#### 响应示例（SQL 数据源）

```json
{
  "datasource_id": "ds_093c5ff90c54",
  "query": "统计2024级各专业的学生人数",
  "generated_query": "SELECT `major`, COUNT(*) AS `student_count` FROM `students` WHERE `enroll_year` = 2024 GROUP BY `major`",
  "columns": ["major", "student_count"],
  "rows": [
    ["计算机科学与技术", 12],
    ["软件工程", 8],
    ["电子信息工程", 10],
    ["数学与应用数学", 7],
    ["英语", 2],
    ["工商管理", 6]
  ],
  "row_count": 6,
  "error": null
}
```

#### 执行流程

```
用户自然语言查询
  ↓
连接数据库 → 自动发现 Schema（表、字段、类型、外键、行数）
  ↓
Schema + 查询 → DeepSeek LLM
  ↓
生成 SQL / ES DSL
  ↓
执行查询 → 返回结构化结果
```

---

## 4. 报告生成

### 4.1 创建报告生成任务

基于数据源内容和/或自然语言查询，生成结构化报告并导出为 DOCX/HTML 文件。

```http
POST /api/v1/conversations/{conversation_id}/reports
```

这是一个**异步接口**，返回 `report_id`，通过轮询查询生成进度。

#### 请求体

```json
{
  "title": "2024级计算机专业学业成绩分析报告",
  "format": ["html", "docx"],
  "report_type": "analysis",
  "datasource_ids": ["ds_093c5ff90c54"],
  "user_query": "分析2024级计算机专业学生成绩，包括各课程平均分、最高分、不及格人数、绩点分布",
  "include_conversation": false,
  "include_citations": true,
  "language": "zh-CN",
  "style": "business",
  "sections": null,
  "metadata": {}
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `title` | string | 是 | - | 报告标题 |
| `format` | string[] | 否 | `["docx", "html"]` | 输出格式: `docx`, `html`, `pdf` |
| `report_type` | string | 否 | `analysis` | 报告类型: `analysis`, `summary`, `research`, `meeting_notes`, `decision_memo` |
| `datasource_ids` | string[] | 否 | `[]` | 引用的数据源 ID 列表 |
| `user_query` | string | 否 | null | 对 SQL/ES 数据源的自然语言查询，触发 Text-to-Query 后再生成报告 |
| `include_conversation` | bool | 否 | true | 是否包含对话上下文 |
| `include_citations` | bool | 否 | true | 是否包含引用来源 |
| `language` | string | 否 | `zh-CN` | 报告语言 |
| `style` | string | 否 | `business` | 报告风格 |
| `sections` | string[] | 否 | null | 自定义章节列表（不填则按 report_type 使用默认章节） |
| `metadata` | object | 否 | `{}` | 附加元数据 |

#### 报告类型默认章节

| 类型 | 默认章节 |
|------|----------|
| `analysis` | 执行摘要, 背景与数据来源, 核心问题分析, 关键发现, 问答洞察总结, 风险与建议, 下一步行动, 附录 |
| `summary` | 概览, 主要问题与回答, 关键结论, 待办事项 |
| `research` | 研究背景, 方法论, 核心发现, 数据分析, 讨论, 结论与建议, 参考资料 |
| `meeting_notes` | 会议基本信息, 参会人员, 讨论内容, 关键决策, 行动项 |
| `decision_memo` | 背景, 问题陈述, 选项分析, 推荐方案, 风险与缓解措施, 执行计划 |

#### 响应示例

```json
{
  "report_id": "rep_1f9d8b129e45",
  "conversation_id": "conv001",
  "status": "queued",
  "created_at": "2026-06-23T10:00:00"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `report_id` | string | 报告任务 ID，用于轮询状态 |
| `conversation_id` | string | 所属会话 ID |
| `status` | string | `queued` → `processing` → `success` / `failed` |
| `created_at` | string | ISO 时间戳 |

---

### 4.2 查询报告状态

轮询报告生成任务的执行状态。当 `status=success` 时，可通过 `artifacts` 中的 URL 下载生成的文件。

```http
GET /api/v1/reports/{report_id}
```

#### 响应示例（生成中）

```json
{
  "report_id": "rep_1f9d8b129e45",
  "conversation_id": "conv001",
  "status": "processing",
  "title": "2024级计算机专业学业成绩分析报告",
  "summary": "",
  "artifacts": [],
  "error": null,
  "created_at": "2026-06-23T10:00:00",
  "updated_at": "2026-06-23T10:00:05",
  "usage": null
}
```

#### 响应示例（生成成功）

```json
{
  "report_id": "rep_1f9d8b129e45",
  "conversation_id": "conv001",
  "status": "success",
  "title": "2024级计算机专业学业成绩分析报告",
  "summary": "报告已基于 1 个数据源生成。",
  "artifacts": [
    {
      "artifact_id": "art_33f27c7fe1bd",
      "format": "html",
      "filename": "rep_1f9d8b129e45.html",
      "url": "/api/v1/artifacts/art_33f27c7fe1bd"
    },
    {
      "artifact_id": "art_fef74ff1ac87",
      "format": "docx",
      "filename": "rep_1f9d8b129e45.docx",
      "url": "/api/v1/artifacts/art_fef74ff1ac87"
    }
  ],
  "error": null,
  "created_at": "2026-06-23T10:00:00",
  "updated_at": "2026-06-23T10:01:27",
  "usage": null
}
```

#### 生成流程

```
POST /reports (用户请求)
  ↓
返回 report_id (status=queued)
  ↓
后台异步执行
  ├─ 收集数据源内容（SQL/ES 自动执行 Text-to-Query）
  ├─ 构建 Prompt → 调用 DeepSeek 生成 ReportSpec
  ├─ 解析 ReportSpec（结构化 JSON）
  ├─ 渲染 HTML
  ├─ 渲染 DOCX
  └─ 注册 Artifact
  ↓
GET /reports/{report_id} (polling)
  └─ status=success → 获取 artifact URL 下载
```

#### 内部 ReportSpec 中间格式

报告生成的核心是**结构化中间格式（ReportSpec）**：

```json
{
  "title": "报告标题",
  "subtitle": "副标题",
  "metadata": { "author": "intelli-engine", "language": "zh-CN" },
  "sections": [
    {
      "heading": "章节标题",
      "content": [
        { "type": "paragraph", "text": "段落文本" },
        { "type": "bullets", "items": ["要点1", "要点2"] },
        { "type": "numbered_list", "items": ["条目1", "条目2"] },
        { "type": "table", "table": { "columns": ["列1", "列2"], "rows": [["值1", "值2"]] } },
        { "type": "code", "code": "代码内容", "language": "python" },
        { "type": "quote", "text": "引用文本" }
      ]
    }
  ],
  "citations": [
    { "id": "src_001", "label": "来源描述", "source_type": "datasource", "locator": "位置说明" }
  ]
}
```

该格式与渲染解耦，一份数据同时生成 DOCX 和 HTML，便于后续扩展 PDF 等格式。

---

## 5. Artifact 下载

下载报告生成结果文件。

```http
GET /api/v1/artifacts/{artifact_id}
```

#### 查询参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `download` | bool | false | 设为 `true` 强制下载而非内联查看 |

#### 响应

- HTML 文件始终以附件形式下载（安全策略）
- DOCX 文件以附件形式下载
- 支持文本文件内联查看（`?download=false` 时）

---

## 6. 数据源配置参考

### 6.1 SQL 数据源

支持的数据库类型及对应驱动：

| db_type | 驱动 | 默认端口 |
|---------|------|----------|
| `mysql` | `mysql+aiomysql` | 3306 |
| `postgresql` | `postgresql+asyncpg` | 5432 |
| `sqlite` | `sqlite+aiosqlite` | - |
| `mssql` | `mssql+aioodbc` | 1433 |
| `oracle` | `oracle+oracledb` | 1521 |

#### 注册示例

```json
{
  "type": "sql",
  "name": "生产数据库",
  "metadata": {
    "db_type": "mysql",
    "host": "192.168.1.100",
    "port": 3306,
    "database": "my_db",
    "username": "readonly",
    "password": "my_password_with@special_chars"
  }
}
```

> 密码中的特殊字符（`@`、`:`、`%` 等）会自动进行 URL 编码，无需手动处理。

---

### 6.2 Elasticsearch 数据源

#### 注册示例

```json
{
  "type": "es",
  "name": "日志搜索引擎",
  "metadata": {
    "hosts": ["http://192.168.1.100:9200"],
    "index": "nginx-access-*",
    "username": "elastic",
    "password": "elastic_password"
  }
}
```

---

## 附录: 完整接口汇总

| 方法 | 路径 | 说明 | 新增 |
|------|------|------|------|
| `GET` | `/api/v1/capabilities` | 能力发现 | ✅ |
| `GET` | `/api/v1/agents` | Agent 清单 | ✅ |
| `POST` | `/api/v1/conversations/{id}/data-sources` | 注册数据源 | ✅ |
| `GET` | `/api/v1/conversations/{id}/data-sources` | 数据源列表 | ✅ |
| `GET` | `/api/v1/conversations/{id}/data-sources/{ds_id}` | 单个数据源 | ✅ |
| `POST` | `/api/v1/conversations/{id}/data-sources/{ds_id}/query` | **自然语言查询** | ✅ |
| `POST` | `/api/v1/conversations/{id}/reports` | **创建报告任务** | ✅ |
| `GET` | `/api/v1/reports/{report_id}` | **报告状态查询** | ✅ |
| `GET` | `/api/v1/artifacts/{artifact_id}` | Artifact 下载 | ✅ |

共 **9 个新增 v1 端点**，涵盖: 能力发现 → 数据源注册 → 自然语言查询 → 报告生成 → 文件下载 的完整链路。
