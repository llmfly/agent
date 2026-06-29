# 报告生成架构

## 1. 六层架构总览

```
                    Lead Agent (内置意图路由)
                        │ 检测到报告需求 → 调 generate_report
                        ▼
┌──────────────────────────────────────┐
│          Planning Layer              │  ← 决定做什么
│  ┌──────────────────────────────┐   │
│  │   Report Planner Agent       │   │  → Business DAG（业务任务）
│  │   Report Template            │   │  → 章节结构（Report Outline）
│  │   Section Definition         │   │  → 每个 Section 所需的 Insight 类型
│  └──────────────────────────────┘   │
│              │                       │
│  ┌──────────────────────────────┐   │
│  │   Execution Planner          │   │  → Business DAG → Execution DAG
│  │   Capability Registry        │   │  → 根据注册的能力展开可执行任务
│  └──────────────────────────────┘   │
└──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────┐
┌──────────────────────────────────────┐
│          Execution Layer             │  ← 只执行 DAG，不知道业务含义
│         Execution Runtime            │
│  schedule() / retry() / parallel()   │
│  checkpoint() / timeout()            │
│              │                       │
│  ┌──────────────────────────────┐   │
│  │   Context Manager            │   │  → 统一装配 Memory/Knowledge/Conversation
│  │   (统一上下文装配)             │   │  → Worker 不直接 retrieve()
│  └──────────────────────────────┘   │
│              │                       │
│  ┌──────────────────────────────┐   │
│  │   Workers (无状态 Tool)       │   │
│  │   SQL / PDF / Search / API   │   │
│  │   DOCX / Memory / ...        │   │
│  └──────────────────────────────┘   │
└──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────┐
│          Evidence Layer              │  ← 标准化、聚合
│       Evidence Aggregator            │
│  List<Evidence> → Evidence Graph     │
│  去重 / 排序 / 关联 / 溯源           │
└──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────┐
│          Analysis Layer              │  ← 可组合的分析 DAG
│          Analysis Graph              │
│  ┌──────────┬──────────┬─────────┐  │
│  │ Trend    │ Risk     │ KPI     │  │
│  │ Analysis │ Analysis │ Analysis│  │
│  ├──────────┼──────────┼─────────┤  │
│  │ Compare  │ Forecast │Summary  │  │
│  └──────────┴──────────┴─────────┘  │
│              │                       │
│  ┌──────────────────────────────┐   │
│  │   Insight Merger             │   │  → 合并所有分析器输出
│  └──────────────────────────────┘   │
└──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────┐
│        Composition Layer             │  ← 按规划填充内容
│         Report Composer              │
│  Section + List<Insight> → Paragraph │
│  不决定章节，只将 Insight 渲染为文字  │
└──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────┐
│          Rendering Layer             │  ← 确定性输出
│    DocxRenderer / HtmlRenderer       │
│  ReportSpec → DOCX / HTML / PDF      │
└──────────────────────────────────────┘
```

### 1.1 核心原则

| 层 | 实现方式 | 职责 | 原因 |
|----|----------|------|------|
| **Intent Layer** | Agent | 理解用户真实需求，判断是否需要报告 | 意图理解需要语义推理 |
| **Planning Layer** | Agent + Workflow | 制定业务计划和执行计划，**决定章节结构** | 规划需要领域知识，Execution Planner 做确定性转换 |
| **Execution Layer** | Runtime | 只执行 Execution DAG，**不知道业务含义** | schedule/retry/parallel/checkpoint 是通用能力 |
| **Evidence Layer** | Workflow | 标准化、去重、排序、构建 Evidence Graph | 确定性数据处理 |
| **Analysis Layer** | Agent (DAG) | 可组合的多分析器并行分析 | 不同分析类型可独立扩展 |
| **Composition Layer** | Agent | 按 Planner 定义的章节填充 Insight → 文字 | 写作是独立的语言表达任务 |
| **Rendering Layer** | Workflow | ReportSpec → 文件 | 纯模板化渲染 |

### 1.2 Workflow 的重新定义

在本架构中，**Workflow 只负责 Execution Runtime**，不是整个流程。

```
Workflow Runtime 只知道：
    TaskA → TaskB → TaskC
    schedule()
    retry()
    parallel()
    checkpoint()
    timeout()

Workflow Runtime 不知道：
    CollectSalesData 是什么意思
    Business Task 是什么
    分析、报告是什么
```

Execution DAG 由 Planning Layer 生成后交给 Runtime 执行，Runtime 不关心业务语义。

---

## 2. Planning Layer

### 2.1 Report Planner Agent

Planner 输出三样东西：

1. **Business DAG** — 业务任务依赖关系
2. **Report Outline** — 报告章节结构
3. **Section → Required Insight** — 每个章节需要哪些类型的 Insight

```json
{
  "title": "华为欧洲市场分析报告",
  "outline": [
    {
      "section_id": "executive_summary",
      "heading": "执行摘要",
      "required_insights": ["summary"]
    },
    {
      "section_id": "market_overview",
      "heading": "欧洲市场概况",
      "required_insights": ["trend", "kpi"]
    },
    {
      "section_id": "sales_analysis",
      "heading": "销售数据分析",
      "required_insights": ["trend", "kpi", "compare"]
    },
    {
      "section_id": "competitive_landscape",
      "heading": "竞争格局",
      "required_insights": ["compare", "risk"]
    },
    {
      "section_id": "risk_assessment",
      "heading": "风险评估",
      "required_insights": ["risk", "forecast"]
    },
    {
      "section_id": "conclusion",
      "heading": "结论与建议",
      "required_insights": ["summary", "forecast"]
    }
  ],
  "business_tasks": [
    {
      "id": "bt_1",
      "name": "CollectSalesData",
      "description": "收集欧洲销量数据",
      "input": {"region": "Europe", "period": "2023-2024"}
    },
    {
      "id": "bt_2",
      "name": "CollectCustomerData",
      "description": "收集欧洲客户信息"
    },
    {
      "id": "bt_3",
      "name": "CollectMarketAnalysis",
      "description": "收集欧洲新能源汽车市场分析"
    },
    {
      "id": "bt_4",
      "name": "CollectCompetitorInfo",
      "description": "收集竞争对手信息"
    }
  ],
  "analysis_requirements": [
    {"type": "trend", "sources": ["bt_1", "bt_3"]},
    {"type": "kpi", "sources": ["bt_1", "bt_2"]},
    {"type": "compare", "sources": ["bt_1", "bt_4"]},
    {"type": "risk", "sources": ["bt_3", "bt_4"]},
    {"type": "forecast", "sources": ["bt_1", "bt_3"]},
    {"type": "summary", "sources": ["*"]}
  ]
}
```

**关键约束**：
- Planner **不知道底层实现**（不知道 SQL、PDF、API）
- Planner **决定章节结构**（Composer 不决定）
- Planner **指定每个章节需要什么类型的 Insight**

### 2.2 Execution Planner

将 Business DAG 转换为 Execution DAG，根据 Capability Registry 和数据源元信息自动展开。

```
CollectSalesData (Business Task)
        │
        ▼
  Execution Planner: 查询 Capability Registry
        │
  ├─ 有 sql 能力 → SQLWorker(task_id, sql_params)
  ├─ 有 api 能力 → APIWorker(task_id, api_params)
  ├─ 有 cache 能力 → CacheWorker(task_id, cache_key)
  └─ 有 memory 能力 → MemoryWorker(task_id, memory_key)

CollectMarketAnalysis (Business Task)
        │
        ▼
  ├─ PDFWorker(task_id, file="annual_report_2024.pdf")
  ├─ SearchWorker(task_id, query="欧洲新能源汽车市场 2024")
  └─ KnowledgeWorker(task_id, vector_query="欧洲新能源汽车")
```

**Execution Planner 不属于 Workflow Runtime**，它属于 Planning Layer。Runtime 只消费它产出的 Execution DAG。

### 2.3 Capability Registry

Capability Registry 替代简单的 Worker Registry，建立能力→Worker→Tool→DataSource 的完整映射：

```
Capability: search
    │
    ├── Worker: HybridSearchWorker
    │       └── Tool: ElasticsearchTool → DataSource: ES Cluster
    │
    └── Worker: WebSearchWorker
            └── Tool: WebSearchTool → DataSource: Bing API

Capability: sql
    │
    ├── Worker: MySQLWorker → Tool: MySQLTool → DataSource: MySQL
    │
    └── Worker: ClickHouseWorker → Tool: ClickHouseTool → DataSource: ClickHouse

Capability: vector_search
    │
    └── Worker: VectorWorker → Tool: MilvusTool → DataSource: Milvus
```

新增数据源（如 Milvus）只需注册新 Worker 和 Tool，**Planner 不需要改**。

---

## 3. Execution Layer

### 3.1 Execution Runtime

Runtime 只消费 Execution DAG，不感知业务语义：

```python
class ExecutionRuntime:
    """只执行 DAG，不知道业务含义。"""
    
    async def execute(self, dag: ExecutionDAG) -> EvidenceGraph:
        """
        1. 拓扑排序
        2. 按层调度 Worker
        3. 重试失败的 Task
        4. 超时控制
        5. Checkpoint（可恢复）
        """
```

**Runtime 的职责**（只有这些）：
- `schedule()` — 按拓扑序调度
- `retry()` — 失败重试（指数退避）
- `parallel()` — 同层任务并行（可配并发数）
- `checkpoint()` — 中间结果持久化，支持断点恢复
- `timeout()` — 任务超时控制

**Runtime 不负责**：
- ❌ Business Task → Execution Task 转换
- ❌ 数据源选择
- ❌ Worker 注册管理
- ❌ 业务含义理解

### 3.2 Context Manager

所有 Worker 不直接 `retrieve()` 上下文。统一由 Context Manager 装配：

```
Context Manager
    │
    ├── Memory Context    → 对话历史、用户偏好
    ├── Knowledge Context → 知识库、文档
    ├── Conversation Context → 当前对话状态
    └── Environment Context  → 配置、权限、数据源凭证
            │
            ▼
         Worker (通过 Context Manager 获取所需上下文)
```

**优势**：
- Worker 不需要知道 Memory 的实现细节
- 新增上下文来源（如环境变量、外部 API）不影响 Worker
- 上下文装配逻辑集中管理，可测试

### 3.3 Worker 接口

```python
class Worker:
    name: str
    capability: str          # 能力标识: sql, pdf, search, ...
    
    async def execute(
        self,
        task: ExecutionTask,
        context: ContextManager,  # 统一上下文入口
    ) -> list[Evidence]:
        """执行任务，返回 Evidence 列表。"""
```

**Worker 设计原则**：
- **无状态** — 同一输入保证同一输出
- **输入明确** — ExecutionTask 包含所有必要参数
- **输出标准化** — 永远是 `List<Evidence>`
- **可重试** — 幂等，失败可安全重试
- **可缓存** — task_id + 参数可作为缓存 key

---

## 4. Evidence Layer

### 4.1 Evidence 数据模型

所有 Worker 的统一输出格式：

```python
class Evidence:
    id: str                              # 全局唯一
    type: EvidenceType                   # sql_row, pdf_chunk, search_result, api_response, ...
    source: SourceInfo                   # 来源追溯
    content: Content                     # 标准化内容
    metadata: dict                       # 额外元信息
    score: float                         # 相关性/置信度
    citation: Citation                   # 引用信息
    relations: list[str]                 # 关联 Evidence ID

class SourceInfo:
    datasource_id: str
    datasource_type: str                 # mysql, pdf, web, api, memory, ...
    document_id: str | None
    table: str | None
    file: str | None
    api: str | None
    url: str | None
    timestamp: str | None

class Content:
    text: str | None
    table: TableContent | None
    image_url: str | None
    structured: dict | None
```

**Worker 输出规范**：
- SQL Worker → `Evidence(type=sql_row, source.table="orders", content.table=...)`
- PDF Worker → `Evidence(type=pdf_chunk, source.document_id="年报.pdf", content.text=...)`
- Search Worker → `Evidence(type=search_result, source.url="...", content.text=..., score=0.92)`
- API Worker → `Evidence(type=api_response, source.api="/api/sales", content.structured=...)`

### 4.2 Evidence Aggregator

```
List<Evidence> (来自所有 Worker)
    │
    ▼
  Evidence Aggregator
    │
    ├─ 标准化字段格式
    ├─ 按 source 去重
    ├─ 按 score 排序
    ├─ 按 relations 关联 → Evidence Graph
    │
    ▼
  Evidence Graph (供 Analysis Layer 消费)
```

---

## 5. Analysis Layer

### 5.1 Analysis Graph（可组合的分析 DAG）

单一 Analysis Agent 改为 **Analysis Graph**，支持多个分析器并行或按依赖执行：

```
Evidence Graph
    │
    ▼
  Analysis Graph
    │
    ├── Trend Analysis    → Insight(type=trend)
    ├── Risk Analysis     → Insight(type=risk)
    ├── KPI Analysis      → Insight(type=kpi)
    ├── Compare Analysis  → Insight(type=compare)
    ├── Forecast          → Insight(type=forecast)
    └── Summary           → Insight(type=summary)
    │
    ▼
  Insight Merger → List<Insight>
```

**Analysis Graph 也是 DAG**，允许分析器之间有依赖关系（如 Summary 依赖其他所有分析器的结果）。

### 5.2 Insight 数据模型

```python
class Insight:
    id: str                              # 唯一标识
    type: InsightType                    # trend, risk, kpi, compare, forecast, summary
    title: str                           # 洞察标题
    finding: str                         # 核心发现，一句话结论
    explanation: str                     # 详细解释
    confidence: float                    # 置信度 0-1
    evidence_refs: list[str]             # 支撑的 Evidence ID 列表
    citations: list[Citation]            # 引用列表
    tags: list[str]                      # 标签
```

### 5.3 新增分析器不需改已有 Prompt

```
需要新增 Policy Analysis：
    1. 注册 Analysis Node: PolicyAnalysis(type=policy)
    2. 在 Planner 的 analysis_requirements 中添加 {type: "policy", ...}
    3. 在 Report Outline 的章节中引用 required_insights: ["policy"]
    
    不需要修改已有的 Trend/Risk/KPI 分析器的 Prompt。
```

### 5.4 与 Planner 的联动

Planner 的 `analysis_requirements` 决定了 Analysis Graph 的构造：

```json
{
  "analysis_requirements": [
    {"type": "trend", "sources": ["bt_1", "bt_3"]},
    {"type": "kpi", "sources": ["bt_1", "bt_2"]},
    {"type": "risk", "sources": ["bt_3", "bt_4"]}
  ]
}
```

Analysis Layer 根据此定义动态组装 Graph。

---

## 6. Composition Layer

### 6.1 Report Composer 职责

Composer **不决定章节结构**，章节结构在 Planning Layer 已经确定。

```python
Composer 的输入:
    - Report Outline（Planner 输出，定义了章节结构）
    - List<Insight>（Analysis Layer 输出）

Composer 的职责:
    - 将 Insight 按章节归类（由每个 section 的 required_insights 决定）
    - 为每个章节撰写段落文字
    - 嵌入表格、数据引用
    - 输出 ReportSpec

Composer 不负责:
    - ❌ 决定报告有哪些章节
    - ❌ 分析原始数据
    - ❌ 推理结论
```

### 6.2 Section + Insight → Paragraph

```
Section: "销售数据分析"
    required_insights: ["trend", "kpi", "compare"]
    
    匹配的 Insight:
    ├── Insight(type=trend,  title="销量增长趋势",  finding="2024年同比增长30%")
    ├── Insight(type=kpi,    title="核心KPI",       finding="毛利率25%...")
    └── Insight(type=compare,title="竞品对比",      finding="华为份额18%...")
    
    Composer 撰写:
    ─────────────────────────────────
    ### 销售数据分析
    
    2024年华为欧洲市场销量同比增长30%...
    
    核心KPI方面，毛利率达到25%...
    
    与竞品对比，华为市场份额为18%...
    ─────────────────────────────────
```

---

## 7. Rendering Layer

与之前一致，Renderer 是确定性输出层：

```python
class BaseRenderer:
    def render(self, spec: ReportSpec) -> bytes: ...
    @property
    def mime_type(self) -> str: ...
    @property
    def file_extension(self) -> str: ...
```

| 渲染器 | 格式 |
|--------|------|
| `DocxRenderer` | .docx |
| `HtmlRenderer` | .html |
| (预留) `PdfRenderer` | .pdf |

---

## 8. 完整数据流

```
Lead Agent (内置意图路由)
    │ 收到用户消息
    │ 判断: 需要生成报告 → 调 generate_report
    ▼
Report Planner Agent
    │ 输出: Business DAG + Report Outline + Analysis Requirements
    ▼
Execution Planner
    │ 查询 Capability Registry, 将 Business DAG → Execution DAG
    ▼
Execution DAG
    │ TaskA(Worker=SQL, params=...)
    │ TaskB(Worker=PDF, params=...)
    │ TaskC(Worker=Search, params=...)
    ▼
Execution Runtime
    │ schedule → retry → parallel → checkpoint
    │ Context Manager 装配上下文供 Worker 使用
    ▼
List<Evidence> (来自所有 Worker)
    ▼
Evidence Aggregator
    │ 去重 → 排序 → 关联 → Evidence Graph
    ▼
Evidence Graph
    ▼
Analysis Graph
    │ Trend Analysis  → Insight(trend)
    │ Risk Analysis   → Insight(risk)
    │ KPI Analysis    → Insight(kpi)
    │ Compare Analysis → Insight(compare)
    │ Forecast        → Insight(forecast)
    │ Summary         → Insight(summary)
    ▼
Insight Merger → List<Insight>
    ▼
Report Composer
    │ Section + Insight → Paragraph
    │ 按 Report Outline 组织章节
    ▼
ReportSpec
    ▼
Renderer → DOCX / HTML / PDF
```

---

## 9. 与当前代码的差异对照

| 当前架构 | 新架构 |
|----------|--------|
| Lead Agent + Workflow 耦合 | 六层分离：Planning → Execution → Evidence → Analysis → Composition → Rendering |
| Workflow 管理整个流程 | Workflow 只作为 Execution Runtime |
| Report Workflow 10 步状态机 | Execution Runtime 只做 schedule/retry/parallel/checkpoint |
| Planner 直接输出 SQL 任务 | Planner → Business DAG → Execution Planner → Execution DAG |
| 单层 QueryTask | Business Task → Execution Task |
| 单一 Analysis Agent | Analysis Graph（可组合的多分析器 DAG） |
| Composer 决定章节 | Planner 决定章节，Composer 只填充内容 |
| Worker 直接 retrieve 上下文 | Context Manager 统一装配 |
| Worker Registry | Capability Registry（能力→Worker→Tool→DataSource） |
| SQL 结果 raw data 喂给 LLM | Evidence 标准化中间格式 |
| 无 Evidence Graph | Evidence Graph 支持去重、排序、关联 |
| Lead Agent 内置意图路由 | Lead Agent 自己判断是否出报告 |
| Keywords 硬编码路由 | Lead Agent 语义路由（通过系统提示词） |

---

## 10. 关键文件索引

| 文件 | 职责 |
|------|------|
| `agents/report_planner.py` | (已删除) Intent 路由由 Lead Agent 内置
| `agents/report_planner.py` | (新建) Report Planner Agent，输出 Business DAG + Outline + Analysis Reqs |
| `agents/analysis_graph.py` | (新建) Analysis Graph，可组合的多分析器编排 |
| `agents/analysis_nodes/trend.py` | (新建) Trend Analysis |
| `agents/analysis_nodes/risk.py` | (新建) Risk Analysis |
| `agents/analysis_nodes/kpi.py` | (新建) KPI Analysis |
| `agents/analysis_nodes/compare.py` | (新建) Compare Analysis |
| `agents/analysis_nodes/forecast.py` | (新建) Forecast |
| `agents/analysis_nodes/summary.py` | (新建) Summary |
| `agents/report_composer.py` | (新建) Report Composer Agent |
| `planning/execution_planner.py` | (新建) Business DAG → Execution DAG |
| `planning/capability_registry.py` | (新建) Capability Registry |
| `runtime/execution_runtime.py` | (新建) 只执行 DAG 的 Runtime |
| `runtime/context_manager.py` | (新建) 统一上下文装配 |
| `runtime/evidence_aggregator.py` | (新建) Evidence → Evidence Graph |
| `workers/base.py` | (新建) Worker 基类 |
| `workers/sql_worker.py` | (新建/重构) SQL Worker |
| `workers/pdf_worker.py` | (新建) PDF Worker |
| `workers/search_worker.py` | (新建) Search Worker |
| `workers/api_worker.py` | (新建) API Worker |
| `workers/memory_worker.py` | (新建) Memory Worker |
| `models/evidence.py` | (新建) Evidence 数据模型 |
| `models/insight.py` | (新建) Insight 数据模型 |
| `schemas/v1/reports.py` | ReportSpec 等 DTO |
| `routers/v1/reports.py` | REST API 路由 |
| `renderers/base.py` | 渲染器基类 |
| `renderers/docx.py` | DOCX 渲染器 |
| `renderers/html.py` | HTML 渲染器 |
