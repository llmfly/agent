# Workspace Data Source Management — 工作空间数据资产管理设计文档

> 版本: v1.0  
> 日期: 2026-06-27  
> 状态: 草稿

---

## 一、设计目标

### 1.1 核心原则

数据源属于 **用户（User）** ，在 **Conversation（对话）** 中 **引用（Reference）**，而不是属于 Conversation。

### 1.2 支持的能力

| 场景 | 是否支持 |
|------|----------|
| 用户只能看到自己的数据源 | ✅ |
| 同一数据源可复用于多个 Conversation | ✅ |
| 新建 Conversation 可选择历史数据源 | ✅ |
| 不选择历史数据源则为空会话 | ✅ |
| Conversation 可随时挂载/卸载数据源 | ✅ |
| 删除 Conversation 不影响数据源 | ✅ |
| 删除数据源后自动解除所有 Conversation 引用 | ✅ |
| 结构化数据（MySQL、ES）与非结构化文件（PDF、Word、TXT 等）统一管理 | ✅ |

---

## 二、数据模型

### 2.1 整体三层架构

```
User
 │
 │ owns
 ▼
DataSource                          ← 数据资产，属于用户
 │
 │ referenced by
 ▼
ConversationDataSource             ← 引用关系，属于 Conversation
 │
 ▼
Conversation                       ← 对话
```

### 2.2 核心表设计

#### datasource — 数据资产

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 所有者 |
| name | VARCHAR(128) | 名称 |
| description | TEXT | 描述 |
| type | VARCHAR(32) | 类型: mysql / postgresql / es / minio / pdf / docx / txt / xlsx / csv |
| status | VARCHAR(20) | 状态: uploading / parsing / embedding / ready / error |
| icon | VARCHAR(64) | 图标 |
| config | JSONB | 连接配置（按类型动态） |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |
| deleted | BOOLEAN | 软删除标记 |

> `config` JSONB 存储示例：
> - MySQL: `{"host": "127.0.0.1", "port": 3306, "database": "prod", "username": "ro", "password": "<encrypted>"}`
> - ES: `{"hosts": ["http://localhost:9200"], "index": "logs", "username": "", "password": ""}`
> - File: `{"object_key": "uploads/user/xxx.pdf", "size": 1024000, "md5": "abc123", "mime": "application/pdf", "parser_status": "done", "embedding_status": "done"}`

#### conversation_datasource — 引用关系

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| conversation_id | UUID | 对话 ID |
| datasource_id | UUID | 数据源 ID |
| alias | VARCHAR(128) | 别名（Agent 看到的是别名而非原名） |
| mount_path | VARCHAR(256) | 挂载路径（文件类） |
| created_at | TIMESTAMP | 创建时间 |

> **别名机制**：Conversation 引用时可设置别名，例如 `mysql_prod` 别名为 `订单库`，Agent 看到的是 `订单库`，支持同一 Conversation 挂载多个同名类型数据源。

### 2.3 关系约束

```
删除 Conversation
  → 不影响 DataSource
  → 级联删除 ConversationDataSource

删除 DataSource
  → 自动解除所有 ConversationDataSource 引用
  → 所有相关 Conversation 自动失效
```

---

## 三、前端页面设计

### 3.1 左侧导航新增

```
💬 Chats
🗂 Data Assets          ← 新增
🧠 Skills
📄 Reports
⚙ Settings
```

### 3.2 Data Assets 首页

```
Data Assets                     [+ Add Data Source]
─────────────────────────────────────────────────────
搜索框 [______________________]  全部 | 数据库 | 文件 | 对象存储

┌─────────────────────────────────────────────────────┐
│ ☐ MySQL Production       MYSQL    ● Connected       │
│   12 Conversations                                    │
├─────────────────────────────────────────────────────┤
│ ☐ Sales PDF              PDF      ● Indexed          │
│   3 Conversations                                     │
├─────────────────────────────────────────────────────┤
│ ☐ Elasticsearch          ES       ● Connected       │
│   0 Conversations                                     │
├─────────────────────────────────────────────────────┤
│ ☐ MinIO Storage          MINIO    ● Connected       │
│   5 Conversations                                     │
└─────────────────────────────────────────────────────┘
```

支持：搜索、排序、类型过滤。

### 3.3 新建数据源流程

点击 `+ Add` → 选择类型 → 动态表单 → 保存

**类型选择：**

```
请选择数据源类型

○ MySQL          ○ PostgreSQL     ○ ClickHouse
○ Elasticsearch  ○ MinIO          ○ S3 / OSS
○ PDF            ○ Word           ○ Excel / CSV
○ TXT            ○ Markdown
```

**动态表单示例（MySQL）：**

```
名称               [________________]
Host               [________________]
Port               [____3306_______]
Username           [________________]
Password           [________________]
Database           [________________]

[Test Connection]  [Save]
```

**文件上传流程：**

```
PDF: sales_report.pdf  [████████████] 100%
状态: Uploading → Parsing → Embedding → Ready
```

### 3.4 Conversation 页面

**实现状态**：✅ 已完成

**顶部数据源栏（`DataSourceBar` 组件）：**

位于对话页面的 header 下方、消息列表上方，展示已关联的数据源并支持快捷操作：

```
┌──────────────────────────────────────────────────────────┐
│  💬 销售数据分析                           [导出] [文件] │  ← header
├──────────────────────────────────────────────────────────┤
│  Data Assets: [mysql_prod ×] [sales.pdf ×]  [+ Attach]  │  ← DataSourceBar
├──────────────────────────────────────────────────────────┤
│                                                          │
│  (消息列表...)                                            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

- **标签展示**：每个已关联的数据源以 `Badge` 形式展示，显示数据源名称（优先显示别名）
- **解除关联**：每个 Badge 带 `×` 按钮，点击直接 detach（无需确认弹窗）
- **新增关联**：右侧 `+ Attach` 按钮，点击打开 Attach 弹窗
- **仅在已有 Thread（非新对话）时显示**：新对话首次提交后才加载 DataSourceBar

**Attach 弹窗（`DataSourceAttachDialog` 组件）：**

```
Attach Data Sources
─────────────────────────────────
选择数据源关联到此对话，Agent 将能访问已关联的数据源。

☐ mysql_prod     (MySQL)              [Attach]
☑ mysql_test     (测试库)  [Alias] [Detach]
☑ sales.pdf      (PDF)                [Detach]
☐ company.pdf    (PDF)                [Attach]

[Close]
```

- 已关联的数据源显示 `[Detach]` 按钮，未关联的显示 `[Attach]`
- 已关联的数据源支持编辑别名（`[Alias]` 按钮）
- 列表分两栏：左侧是数据源信息（名称、类型 Badge），右侧是操作按钮
- 关闭弹窗后自动刷新 DataSourceBar

### 3.5 新 Conversation 初始化

点击 `New Chat` 先弹初始化窗口：

```
New Conversation
─────────────────────────────────
Title: [________________________]

Select Data Sources
☑ mysql_prod
☐ sales.pdf
☐ es_log
☐ minio

[Skip]  [Create]
```

选择 `Skip` 则创建空会话，后续可随时 Attach。

### 3.6 聊天侧边栏 — Attached Data Sources

```
Attached Data Sources
─────────────────────────
MYSQL
  订单库 ● Connected     ⋮

PDF
  sales.pdf ● Indexed    ⋮

MINIO
  assets ● Connected     ⋮
```

每个数据源支持：
- **Rename Alias** — 重命名别名
- **Detach** — 解除引用（不删除数据源）
- **View Detail** — 查看详情

### 3.7 数据源详情页

```
MySQL Production          MYSQL    ● Connected
────────────────────────────────────────
Created: Yesterday     Used By: 12 Conversations

Connection
─────────────────────────
Host:     192.168.1.100
Port:     3306
Database: prod
Username: readonly

[Edit] [Reconnect] [Delete]
```

**文件类型详情：**

```
sales.pdf                 PDF      ● Ready
────────────────────────────────────────
Upload: 2026-06-26    Size: 2.3 MB
Embedding: Complete    Chunks: 582    Vectors: 582

[Re-parse] [Re-embed] [Download] [Delete]
```

---

## 四、权限隔离

采用 **两级隔离**：

```
User
 ├── Data Sources（用户私有资产）
 │
 └── Conversations
        │
        └── ConversationDataSource（引用关系）
```

- 用户只能看到和操作自己的数据源
- Conversation 只存引用，不拥有数据
- 数据源删除后，所有 Conversation 引用自动失效

---

## 五、后端 API 设计

### 5.1 数据源 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/data-sources` | 创建数据源 |
| GET | `/api/v1/data-sources` | 列表（支持搜索/过滤/分页） |
| GET | `/api/v1/data-sources/{id}` | 详情 |
| PUT | `/api/v1/data-sources/{id}` | 更新配置 |
| DELETE | `/api/v1/data-sources/{id}` | 删除（软删） |
| POST | `/api/v1/data-sources/{id}/test` | 测试连接 |

### 5.2 引用管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/conversations/{id}/datasources` | Attach 数据源 |
| GET | `/api/v1/conversations/{id}/datasources` | 已 Attach 列表 |
| DELETE | `/api/v1/conversations/{id}/datasources/{ds_id}` | Detach |
| PUT | `/api/v1/conversations/{id}/datasources/{ds_id}` | 更新别名 |

### 5.3 文件上传

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/data-sources/upload` | 上传文件（返回 object_key） |
| GET | `/api/v1/data-sources/{id}/parse-status` | 解析/Embedding 状态 |

---

## 六、数据源类型抽象

```
DataSource
 │
 ├── Structured (Connector → Schema → SQL Query)
 │     MySQL / PostgreSQL / ClickHouse / SQLServer
 │     Oracle / Hive / Doris / StarRocks
 │
 ├── Search Engine
 │     Elasticsearch
 │
 ├── Object Storage
 │     MinIO / OSS / COS / S3
 │
 ├── Files (Upload → Parse → Chunk → Embedding → Vector)
 │     PDF / Word / TXT / Markdown / Excel / CSV / PPT
 │
 └── API / MCP
       REST API / GraphQL / MCP Server
```

**统一 Agent 访问接口：**

```
DataSource
  ↓
Connector
  ↓
Loader
  ↓
Parser / Schema Reader
  ↓
Retriever (SQL / Vector / Full-Text)
```

Agent 无需关心底层数据源类型，统一通过 Retriever 获取数据。

---

## 七、与当前系统的迁移方案

### 7.1 当前状态

- `_data_sources` 是进程级内存字典，按 `conversation_id` 分组
- 数据源不存在持久化到 DB
- 多 worker 下存在数据不一致问题

### 7.2 迁移步骤

1. **新建 `datasource` 表** — 将数据源从内存迁移到 DB
2. **新建 `conversation_datasource` 表** — 引用关系表
3. **保留内存缓存** — 作为热路径加速，DB 作为持久化层
4. **API 升级** — 现有 v1 接口保持兼容，新增用户级数据源接口
5. **前端适配** — 新增 Data Assets 页面
6. **存量数据迁移脚本** — 将 `threads_meta.metadata._v1_data_sources` 中的数据迁移到新表

### 7.3 向后兼容

- 旧 API（`/api/v1/conversations/{id}/data-sources`）保持可用
- 新 API 和旧 API 共享同一份数据源池
- 前端逐步迁移到新页面

---

## 八、推荐的产品形态参考

参考企业级 AI 产品设计思路：

- **NotebookLM** — 数据源作为知识库管理
- **Dify** — 知识库/数据集独立管理
- **Open WebUI** — 工作空间文件管理
- **Cursor Workspace** — 项目级上下文管理

核心思路：**聊天（Conversation）只是引用（Attach）数据资产，而不是拥有它们。**

这套架构的扩展性支持：
- 未来接入更多数据源类型
- Agent Workflow 多步数据消费
- RAG 检索增强生成
- 数据血缘追踪
- 数据源共享与协作
