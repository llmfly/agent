# 报告生成架构 V2：重构设计文档

> 基于 V1 架构评审的 P0 项重构设计（Intent Router + ContextBuilder + Executor Registry + Validation Layer）。
>
> 目标：解耦 Lead Agent 的路由职责，模块化 Context 构建，插件化执行器，引入质量校验层。

---

## 目录

1. [总体架构变化](#1-总体架构变化)
2. [Intent Router](#2-intent-router)
3. [ContextBuilder](#3-contextbuilder)
4. [Executor Registry](#4-executor-registry)
5. [Validation Layer](#5-validation-layer)
6. [迁移计划](#6-迁移计划)
7. [文件变更清单](#7-文件变更清单)

---

## 1. 总体架构变化

### V1 架构（当前）

```
User → build_run_create_request (God Function)
        → Lead Agent (路由 + 对话 + 工具调用)
            → generate_report Tool → ReportPipeline (6层)
```

### V2 架构（目标）

```
User
  │
  ▼
ContextBuilder          ← 新：模块化上下文构建
  │
  ▼
Intent Router           ← 新：独立意图分类器
  │
  ├─ ChatIntent    → ChatAgent（原 Lead Agent 的对话能力）
  ├─ ReportIntent  → Workflow Runtime → ReportPipeline → Validator
  ├─ ResearchIntent→ Workflow Runtime → DeepResearchPipeline
  ├─ AnalysisIntent→ Workflow Runtime → AnalysisPipeline
  └─ SkillIntent   → SkillRuntime
```

### 关键变化

| 变化 | V1 | V2 |
|---|---|---|
| 意图识别 | 关键词匹配 + LLM prompt 引导 | 独立 `IntentClassifier`（few-shot + schema） |
| Context 构建 | `build_run_create_request` 单函数 | `ContextBuilder` 责任链模式 |
| 执行器注册 | `CapabilityRegistry` + 硬编码 worker 注册 | `ExecutorRegistry` 插件式注册 |
| 数据校验 | 无（fail-fast 仅检查"是否为空"） | `ValidationLayer` 结构化数据校验 |
| Lead Agent | 路由 + 对话 + 工具调用 | 仅对话（ChatAgent） |

---

## 2. Intent Router

### 2.1 设计目标

- 将意图识别从 Lead Agent 的 prompt 中剥离
- 支持可扩展的意图类型，不污染对话 prompt
- 识别准确率高于当前的关键词匹配

### 2.2 接口定义

```python
# ── 意图枚举 ──────────────────────────────────────────────

class IntentType(str, Enum):
    CHAT = "chat"              # 普通对话
    REPORT = "report"          # 生成报告
    RESEARCH = "research"      # 深度研究（多轮搜索+分析）
    ANALYSIS = "analysis"      # 数据分析（查询+可视化，不出文档）
    SKILL = "skill"            # Skill 调用
    WORKFLOW = "workflow"      # 自定义工作流


@dataclass
class IntentResult:
    intent: IntentType
    confidence: float
    # 用于后续 Routing 的元数据
    metadata: dict[str, Any] = field(default_factory=dict)
    # 路由原因（日志/调试用）
    reason: str = ""


# ── 分类器接口 ────────────────────────────────────────────

class IntentClassifier(ABC):
    """意图分类器基类。支持多策略实现。"""

    @abstractmethod
    async def classify(
        self,
        user_message: str,
        context: BuildContext,
    ) -> IntentResult:
        ...


# ── 路由结果 ──────────────────────────────────────────────

@dataclass
class RouteDecision:
    intent: IntentResult
    # 路由目标（graph node name 或 workflow id）
    target: str
    # 路由前需要注入的上下文
    context_updates: dict[str, Any] = field(default_factory=dict)
```

### 2.3 实现策略：多层分类

```
Layer 1: 关键词快速匹配（~0ms, 无 LLM 调用）
  ├─ 检测"报告/文档/导出" → REPORT (high confidence)
  ├─ 检测"研究/调研/Deep Research" → RESEARCH (high confidence)
  ├─ 检测"分析/查询/统计" → ANALYSIS (medium confidence)
  └─ 不匹配 → 进入 Layer 2

Layer 2: LLM Few-shot 分类（~200ms, 1 次 LLM 调用）
  ├─ 输入: user_message + context 摘要
  ├─ 输出: IntentType + confidence
  └─ 用于模糊/复合意图

Layer 3: Fallback → CHAT
```

### 2.4 路由流程

```
                   User Message
                        │
                        ▼
                 ContextBuilder
                  (见第 3 节)
                        │
                        ▼
              IntentClassifier
                        │
              ┌─────────┼─────────┐
              ▼         ▼         ▼
         confidence   medium    low/high
          > 0.95 ?   confidence  confidence
              │         │         │
              │         ▼         ▼
              │    LLM Layer   ChatAgent
              │    (Layer 2)   (fallback)
              │         │
              ▼         ▼
        Workflow     IntentResult
        Runtime
```

### 2.5 路由表

| Intent | Target | Required Context |
|---|---|---|
| `REPORT` | `WorkflowRuntime.run("report", ...)` | datasource_metadata, schema_summary, document_path |
| `RESEARCH` | `WorkflowRuntime.run("deep_research", ...)` | search_config, depth, max_sources |
| `ANALYSIS` | `WorkflowRuntime.run("analysis", ...)` | datasource_metadata, visualization_prefs |
| `SKILL` | `SkillRuntime.run(skill_name, ...)` | skill_config, skill_params |
| `CHAT` | `ChatAgent.invoke(...)` | conversation_history, memory |
| `WORKFLOW` | `WorkflowRuntime.run(workflow_id, ...)` | workflow_definition, input_params |

### 2.6 与 V1 的差异

| 维度 | V1（关键词匹配） | V2（Intent Router） |
|---|---|---|
| 意图类型 | 仅 report / non-report | 6 种 + 可扩展 |
| 检测精度 | 关键词命中制（低召回） | 多层分类（高精度 + 高召回） |
| LLM 调用 | 0 次检测 + Lead Agent prompt 引导 | 0-1 次（模糊意图时才需 LLM） |
| 路由逻辑 | 嵌入在 Lead Agent prompt 中 | 独立模块，可测试 |
| 扩展新意图 | 修改 Lead Agent prompt | 新增 IntentType + 路由目标 |

---

## 3. ContextBuilder

### 3.1 设计目标

- 将 `build_run_create_request` 拆分为单一职责组件
- 支持责任链模式，新增 Context 维度无需修改适配器
- 组件可独立测试、可替换

### 3.2 接口定义

```python
# ── 构建上下文 ────────────────────────────────────────────

@dataclass
class BuildContext:
    """ContextBuilder 的中间结果，逐层累积。"""
    # 原始输入
    body: ConversationMessageRequest
    external_context: ExternalContext
    selected_data_sources: list[dict[str, Any]] | None

    # 逐层构建的产物
    metadata: dict[str, Any] = field(default_factory=dict)
    messages: list[dict] = field(default_factory=list)
    system_instructions: str = ""
    datasource_message: str = ""
    user_message: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    intent: IntentResult | None = None

    # 运行配置
    run_config: dict[str, Any] = field(default_factory=dict)


class ContextBuilderComponent(ABC):
    """ContextBuilder 的责任链组件。

    每个组件只负责构建 BuildContext 的一个维度。
    组件之间通过 BuildContext 传递中间结果，互不感知。
    """

    @abstractmethod
    async def build(self, ctx: BuildContext) -> BuildContext:
        ...


class ContextBuilder:
    """上下文构建器，编排责任链。"""

    def __init__(self, components: list[ContextBuilderComponent] | None = None):
        self._components = components or self._default_components()

    def _default_components(self) -> list[ContextBuilderComponent]:
        return [
            MetadataBuilder(),
            ModeConfigBuilder(),
            DatasourceInstructionBuilder(),
            DatasourceMessageBuilder(),
            IntentClassifierComponent(),
            MessageAssembler(),
        ]

    async def build(self, body, external_context, selected_data_sources=None) -> RunCreateRequest:
        ctx = BuildContext(
            body=body,
            external_context=external_context,
            selected_data_sources=selected_data_sources,
        )
        for component in self._components:
            ctx = await component.build(ctx)
        return self._to_run_create_request(ctx)

    @staticmethod
    def _to_run_create_request(ctx: BuildContext) -> RunCreateRequest:
        return RunCreateRequest(
            assistant_id=ctx.body.agent_id,
            input={"messages": ctx.messages},
            metadata=ctx.metadata,
            context={**ctx.context, **(ctx.intent.to_dict() if ctx.intent else {})},
            stream_mode=["messages-tuple", "values", "updates", "custom", "events"],
            stream_subgraphs=True,
            stream_resumable=True,
            on_disconnect="cancel",
        )
```

### 3.3 组件职责

```
ContextBuilder
  ├── MetadataBuilder
  │   职责：从 body + external_context 构建 metadata
  │   包含：user_id, datasource_ids, external_user 等
  │   对应 V1: build_external_metadata + inject_external_user
  │
  ├── ModeConfigBuilder
  │   职责：从 body.options 解析运行配置
  │   包含：mode, model, thinking, reasoning_effort, subagent 等
  │   对应 V1: _context_from_options
  │
  ├── DatasourceInstructionBuilder
  │   职责：构建数据源系统指令（Few-shot 示例）
  │   包含：数据源数量描述 + 正反例
  │   对应 V1: _format_data_sources_for_prompt / _NO_SOURCE_INSTRUCTIONS
  │
  ├── DatasourceMessageBuilder
  │   职责：构建数据源详细信息的 system message（XML）
  │   包含：表结构、文件路径、预览等
  │   对应 V1: _build_datasource_system_message
  │
  ├── IntentClassifierComponent
  │   职责：调用 IntentClassifier 识别意图
  │   输出：IntentResult → 写入 ctx.intent
  │   新增：V1 中由 _detect_report_intent + Lead Agent 共同完成
  │
  └── MessageAssembler
      职责：组装最终 messages 数组
      顺序：system 指令 → datasource message → human message
      对应 V1: build_run_create_request 中的 messages 组装逻辑
```

### 3.4 新增 Context 维度的方式

```python
# 示例：新增 KnowledgeContext 组件
class KnowledgeContextBuilder(ContextBuilderComponent):
    """注入知识库上下文。"""

    async def build(self, ctx: BuildContext) -> BuildContext:
        if not ctx.selected_data_sources:
            return ctx
        # 从 selected_data_sources 中提取 knowledge 类型
        knowledge_sources = [
            ds for ds in ctx.selected_data_sources
            if ds.get("type") == "knowledge"
        ]
        if not knowledge_sources:
            return ctx
        # 构建 knowledge 系统消息
        knowledge_msg = self._build_knowledge_message(knowledge_sources)
        # 插入到 system instructions 之后
        ctx.messages.insert(-1, {  # 在 human 消息之前
            "type": "system",
            "content": [{"type": "text", "text": knowledge_msg}],
        })
        return ctx
```

**只需**：

1. 新建 `KnowledgeContextBuilder` 实现 `ContextBuilderComponent`
2. 在 `ContextBuilder._default_components()` 中注册
3. 无需修改其他任何组件

### 3.5 与 V1 差异

| 维度 | V1（build_run_create_request） | V2（ContextBuilder） |
|---|---|---|
| 职责 | 7+ 个职责耦合 | 每个组件 1 个职责 |
| 可测试性 | 需要 mock 整个函数 | 每个组件可独立单元测试 |
| 扩展性 | 修改 god function | 新增组件 + 注册 |
| 代码行数 | ~370 行单文件 | 每个组件 ~30-60 行 |
| 迁移成本 | - | 可逐步替换，兼容旧接口 |

---

## 4. Executor Registry

### 4.1 设计目标

- 将 Worker 注册从 Pipeline 中解耦，改为声明式注册
- 支持运行时按需注册/注销 Executor
- 统一的 Executor 接口，新增执行器无需修改调度代码
- 当前的 `CapabilityRegistry` 骨架不错，但需要：

  1. 去掉 Pipeline 中的硬编码 worker 注册
  2. 支持 Executor 元数据（描述、输入 schema、输出 schema）
  3. 支持 Executor 发现（文件系统扫描 / 装饰器自动注册）

### 4.2 接口定义

```python
# ── Executor 元数据 ───────────────────────────────────────

@dataclass
class ExecutorMetadata:
    """Executor 的声明式元数据。"""
    name: str                          # 唯一名称，如 "sql_executor"
    capability: str                    # 能力标签，如 "sql"
    description: str = ""
    input_schema: dict[str, Any] | None = None   # JSON Schema
    output_schema: dict[str, Any] | None = None
    tags: list[str] = field(default_factory=list)  # 如 ["builtin", "datasource"]


# ── Executor 接口 ─────────────────────────────────────────

class BaseExecutor(ABC):
    """Executor 基类（替代 BaseWorker）。

    相比 BaseWorker 的改进：
    1. 声明式 metadata（替代 name + capability 字段）
    2. 支持 validate 阶段（见第 5 节）
    3. 统一的 error 返回格式
    """

    metadata: ExecutorMetadata

    @abstractmethod
    async def execute(self, task: ExecutionTask, context: dict[str, Any]) -> list[Evidence]:
        ...

    async def validate_input(self, task: ExecutionTask) -> list[str]:
        """预执行校验。返回 warning 列表。"""
        return []

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def capability(self) -> str:
        return self.metadata.capability


# ── 执行器注册表 ──────────────────────────────────────────

class ExecutorRegistry:
    """执行器注册表。

    替代 CapabilityRegistry。改进：
    1. 支持声明式注册（装饰器 + 文件扫描）
    2. 支持 Executor 元数据查询
    3. 支持优先级和覆盖
    """

    def __init__(self):
        self._executors: dict[str, BaseExecutor] = {}
        self._capability_map: dict[str, list[str]] = {}

    # ── 注册 ──────────────────────────────────────────────

    def register(self, executor: BaseExecutor) -> None:
        assert executor.name not in self._executors, \
            f"Executor {executor.name} already registered"
        self._executors[executor.name] = executor
        cap = executor.capability
        self._capability_map.setdefault(cap, []).append(executor.name)

    def register_all(self, executors: list[BaseExecutor]) -> None:
        for ex in executors:
            self.register(ex)

    # ── 发现 ──────────────────────────────────────────────

    @classmethod
    def discover(cls, *paths: str) -> list[BaseExecutor]:
        """从指定路径扫描并实例化 Executor。

        搜索规则：
        - 文件名匹配 *_executor.py
        - 模块内所有 BaseExecutor 子类（非抽象）自动实例化
        - 支持通过 ``__init_subclass__`` 的元数据注册
        """
        # 实现略 — 使用 importlib + inspect
        ...

    # ── 查询 ──────────────────────────────────────────────

    def get_executor(self, name: str) -> BaseExecutor | None:
        return self._executors.get(name)

    def get_executors(self, capability: str) -> list[BaseExecutor]:
        names = self._capability_map.get(capability, [])
        return [self._executors[n] for n in names if n in self._executors]

    def has_capability(self, capability: str) -> bool:
        return capability in self._capability_map and bool(self._capability_map[capability])

    def list_capabilities(self) -> list[str]:
        return list(self._capability_map.keys())

    def list_executors(self) -> list[BaseExecutor]:
        return list(self._executors.values())

    # ── 生命周期 ──────────────────────────────────────────

    def unregister(self, name: str) -> None:
        executor = self._executors.pop(name, None)
        if executor:
            cap = executor.capability
            if cap in self._capability_map:
                self._capability_map[cap] = [n for n in self._capability_map[cap] if n != name]


# ── 装饰器支持（可选） ─────────────────────────────────────

_registry: ExecutorRegistry | None = None

def get_executor_registry() -> ExecutorRegistry:
    global _registry
    if _registry is None:
        _registry = ExecutorRegistry()
    return _registry


def register_executor(cls: type[BaseExecutor]) -> type[BaseExecutor]:
    """类装饰器：自动注册 Executor。"""
    get_executor_registry().register(cls())
    return cls


# ── 使用示例 ──────────────────────────────────────────────

@register_executor
class SQLExecutor(BaseExecutor):
    metadata = ExecutorMetadata(
        name="sql_executor",
        capability="sql",
        description="执行 SQL 查询并返回结果",
        tags=["builtin", "datasource"],
    )

    async def execute(self, task, context):
        # ... 执行 SQL 查询
        ...
```

### 4.3 Pipeline 集成变化

**V1（当前 — 硬编码在 Pipeline 中）：**

```python
# report_pipeline.py — ~30 行硬编码 worker 注册
registry = get_capability_registry()
registry.register_worker(SQLWorker())
registry.register_worker(PdfWorker())
registry.register_worker(DocxWorker())
# ...
worker_map = {}
for cap in registry.list_capabilities():
    workers = registry.get_workers(cap)
    for w in workers:
        worker_map[w.name] = w
```

**V2（声明式注册）：**

```python
# executors/__init__.py — 自动发现
from deerflow.executor_registry import get_executor_registry, BaseExecutor
import importlib, pkgutil, inspect

registry = get_executor_registry()
for module_info in pkgutil.iter_modules(__path__):
    module = importlib.import_module(f"{__name__}.{module_info.name}")
    for name, obj in inspect.getmembers(module):
        if (inspect.isclass(obj) and issubclass(obj, BaseExecutor)
                and not inspect.isabstract(obj)):
            registry.register(obj())

# report_pipeline.py — 只需一行
executor_registry = get_executor_registry()
worker_map = {e.name: e for e in executor_registry.list_executors()}
```

### 4.4 内置 Executor 列表

| Executor | Capability | 来源 | 备注 |
|---|---|---|---|
| `SQLExecutor` | `sql` | V1 `SQLWorker` | 迁移 |
| `PdfExecutor` | `document_parse` | V1 `PdfWorker` | 迁移 |
| `DocxExecutor` | `document_parse` | V1 `DocxWorker` | 迁移 |
| `ExcelExecutor` | `document_parse` | V1 `ExcelWorker` | 迁移 |
| `TextExecutor` | `document_parse` | V1 `TextWorker` | 迁移 |
| `SearchExecutor` | `search` | 新增 | 预留 |
| `PythonExecutor` | `code_execution` | 新增 | 预留 |
| `ChartExecutor` | `visualization` | 新增 | 预留 |
| `RAGExecutor` | `rag` | 新增 | 预留 |

### 4.5 迁移方案

```
Phase 1: 新增 BaseExecutor + ExecutorRegistry（与 CapabilityRegistry 共存）
Phase 2: 逐个将 BaseWorker 子类适配为 BaseExecutor
          （Executor 内部可组合 Worker，反之亦然）
Phase 3: 删除 CapabilityRegistry + BaseWorker，完全切换
```

---

## 5. Validation Layer

### 5.1 设计目标

- 在 Execution 和 Composition 之间增加质量校验层
- 校验数据是否有效、完整、可用
- 提供结构化错误信息，支持自动修复或跳过
- 不阻断正常流程，只阻断"脏数据"进入 Composer

### 5.2 位置

```
Execution Layer
    │
    ▼
Validator Layer         ← 新增
    │
    ├── Pass → EvidenceAggregator → Analysis → Composition
    │
    └── Fail → 修复尝试 → 重试或跳过 → 标记脏数据
                    │
                    ▼
              ReportComposer 会收到
              valid_evidence + warning（脏数据详情）
```

### 5.3 接口定义

```python
# ── 校验结果 ──────────────────────────────────────────────

@dataclass
class ValidationResult:
    """单个 Evidence 的校验结果。"""
    evidence_id: str
    passed: bool
    severity: str = "error"   # "error" | "warning" | "info"
    checks: list[CheckResult] = field(default_factory=list)
    auto_fixed: bool = False


@dataclass
class CheckResult:
    """单条校验检查的结果。"""
    check_name: str
    passed: bool
    message: str = ""
    fix_suggestion: str = ""


@dataclass
class ValidationReport:
    """整个批次的校验报告。"""
    total: int = 0
    passed: int = 0
    failed: int = 0
    auto_fixed: int = 0
    results: list[ValidationResult] = field(default_factory=list)
    # 通过校验的证据（含 auto-fixed 的）
    valid_evidence: list[Evidence] = field(default_factory=list)
    # 未通过但标记为 warning 的证据（Composer 可见但标记）
    warning_evidence: list[tuple[Evidence, ValidationResult]] = field(default_factory=list)
    # 完全失败的证据（Composer 不可见）
    failed_evidence: list[tuple[Evidence, ValidationResult]] = field(default_factory=list)


# ── 校验器接口 ────────────────────────────────────────────

class EvidenceValidator(ABC):
    """证据校验器基类。每个校验器只负责一个维度。"""

    @abstractmethod
    async def validate(self, evidence: Evidence) -> list[CheckResult]:
        ...


# ── 内置校验器 ────────────────────────────────────────────

class SQLEmptyResultValidator(EvidenceValidator):
    """SQL 查询是否返回空结果。"""

    async def validate(self, evidence: Evidence) -> list[CheckResult]:
        results = []
        if evidence.source.datasource_type != "sql":
            return results
        content = evidence.content
        if not content.text and not content.table:
            results.append(CheckResult(
                check_name="sql_empty",
                passed=False,
                message="SQL 查询未返回数据",
                fix_suggestion="检查 SQL 语句或数据源连接",
            ))
        return results


class FileExistsValidator(EvidenceValidator):
    """文件是否存在、是否可读。"""

    async def validate(self, evidence: Evidence) -> list[CheckResult]:
        results = []
        if evidence.source.datasource_type not in ("pdf", "docx", "txt"):
            return results
        file_path = evidence.source.document_id or ""
        if file_path and not Path(file_path).exists():
            results.append(CheckResult(
                check_name="file_not_found",
                passed=False,
                message=f"文件不存在: {file_path}",
                fix_suggestion="检查文件路径或重新上传",
            ))
        return results


class ContentLengthValidator(EvidenceValidator):
    """内容长度是否合理。"""

    async def validate(self, evidence: Evidence) -> list[CheckResult]:
        results = []
        text = evidence.content.text or ""
        if len(text.strip()) < 10 and not evidence.content.table:
            results.append(CheckResult(
                check_name="content_too_short",
                passed=False,
                severity="warning",
                message=f"证据内容过短 ({len(text.strip())} 字符)",
                fix_suggestion="检查数据源是否正确",
            ))
        return results


class JSONValidator(EvidenceValidator):
    """JSON 内容是否合法。"""

    async def validate(self, evidence: Evidence) -> list[CheckResult]:
        results = []
        if evidence.content.mime_type != "application/json":
            return results
        try:
            if evidence.content.text:
                json.loads(evidence.content.text)
        except json.JSONDecodeError as e:
            results.append(CheckResult(
                check_name="invalid_json",
                passed=False,
                message=f"JSON 解析失败: {e}",
                fix_suggestion="检查数据源返回格式",
            ))
        return results


# ── 校验器引擎 ────────────────────────────────────────────

class ValidationEngine:
    """校验引擎，编排多个 EvidenceValidator。"""

    def __init__(self, validators: list[EvidenceValidator] | None = None):
        self._validators = validators or self._default_validators()

    @staticmethod
    def _default_validators() -> list[EvidenceValidator]:
        return [
            SQLEmptyResultValidator(),
            FileExistsValidator(),
            ContentLengthValidator(),
            JSONValidator(),
        ]

    async def validate_all(self, evidence_list: list[Evidence]) -> ValidationReport:
        """对全部证据执行所有校验。"""
        report = ValidationReport(total=len(evidence_list))

        for ev in evidence_list:
            all_checks: list[CheckResult] = []
            for validator in self._validators:
                checks = await validator.validate(ev)
                all_checks.extend(checks)

            # 聚合校验结果
            errors = [c for c in all_checks if not c.passed and c.severity in ("error",)]
            warnings = [c for c in all_checks if not c.passed and c.severity == "warning"]

            result = ValidationResult(
                evidence_id=ev.id,
                passed=len(errors) == 0,
                checks=all_checks,
            )

            if result.passed and not warnings:
                report.passed += 1
                report.valid_evidence.append(ev)
            elif result.passed and warnings:
                report.passed += 1
                report.warning_evidence.append((ev, result))
                report.valid_evidence.append(ev)  # warning 的证据仍然可用
            else:
                report.failed += 1
                report.failed_evidence.append((ev, result))

            report.results.append(result)

        report.auto_fixed = 0  # 预留自动修复
        return report
```

### 5.4 校验规则矩阵

| 校验器 | Evidence 类型 | 校验规则 | Severity |
|---|---|---|---|
| `SQLEmptyResultValidator` | `sql` | SQL 结果非空 | `error` |
| `FileExistsValidator` | `pdf/docx/txt` | 文件路径存在 | `error` |
| `ContentLengthValidator` | all | 内容 >= 10 字符 | `warning` |
| `JSONValidator` | `application/json` | JSON 解析成功 | `error` |
| `SchemaComplianceValidator` | `sql` | 列名与 schema 一致 | `warning` |
| `ScoreThresholdValidator` | all | confidence > 0.3 | `warning` |

### 5.5 Pipeline 集成

```python
# report_pipeline.py — V2 集成

class ReportPipeline:
    async def run(self, ...):
        # Layer 1-2: Planning + Execution（不变）
        ...

        # ── NEW: Validation Layer (between Execution and Evidence) ──
        self._log_layer(2.5, "校验证据质量")
        validation_engine = ValidationEngine()
        validation_report = await validation_engine.validate_all(all_evidence)

        logger.info(
            "[Pipeline] Validation: %d passed, %d warnings, %d failed",
            validation_report.passed,
            len(validation_report.warning_evidence),
            len(validation_report.failed_evidence),
        )

        # 校验后，只将 valid + warning 证据传给后续层
        filtered_evidence = (
            validation_report.valid_evidence
            + [ev for ev, _ in validation_report.warning_evidence]
        )

        if not filtered_evidence:
            raise RuntimeError(
                "所有证据均未通过质量校验，终止管道"
            )

        # Layer 3: Evidence（接收已过滤的证据）
        evidence_graph = self._evidence_aggregator.aggregate(filtered_evidence)
        ...
```

### 5.6 与 V1 差异

| 维度 | V1 | V2 |
|---|---|---|
| 数据校验 | 无（仅在 Evidence 为空时 fail-fast） | 结构化校验矩阵 |
| 错误粒度 | 整批成功/失败 | 单个 Evidence 级别 |
| 告警机制 | 无 | warning 级校验不阻断流程 |
| 自动修复 | 无 | 预留接口 |
| Composer 可见性 | 全部证据 | 仅 valid + warning 证据 |

---

## 6. 迁移计划

### Phase 1：ContextBuilder 拆分（当前 sprint）

**目标**：将 `build_run_create_request` 拆为责任链模式，不改动外部行为。

| 步骤 | 内容 | 涉及文件 | 风险 |
|---|---|---|---|
| 1.1 | 定义 `BuildContext` + `ContextBuilderComponent` 接口 | `backend/app/gateway/services_v1/context_builder.py` | 低（新文件） |
| 1.2 | 逐个提取 Component | `MetadataBuilder`, `ModeConfigBuilder`, `DatasourceInstructionBuilder`, `DatasourceMessageBuilder`, `MessageAssembler` | 低（逐组件替换） |
| 1.3 | 保留 `build_run_create_request` 作为向后兼容的包装函数 | `run_adapter.py` | 低（调用方不变） |
| 1.4 | 对接外部测试，验证行为一致 | - | 中 |

### Phase 2：Intent Router（当前 sprint）

**目标**：新增意图分类器，在不删除旧逻辑的前提下并行运行。

| 步骤 | 内容 | 涉及文件 | 风险 |
|---|---|---|---|
| 2.1 | 定义 `IntentType`, `IntentResult`, `IntentClassifier` 接口 | `backend/app/gateway/routing/intent_classifier.py` | 低（新文件） |
| 2.2 | 实现 `KeywordIntentClassifier`（迁移 V1 关键词逻辑） | 同上 | 低 |
| 2.3 | 实现 `LLMIntentClassifier`（few-shot 分类） | 同上 | 中（需要调优） |
| 2.4 | 实现 `MultiLayerIntentClassifier`（组合策略） | 同上 | 中 |
| 2.5 | 在 `ContextBuilder` 中集成 `IntentClassifierComponent` | `context_builder.py` | 低 |
| 2.6 | 添加独立路由图（`/api/routing/classify` 端点） | 新增 router | 低 |

### Phase 3：Executor Registry + Validation Layer（下个 sprint）

**目标**：将 Worker 注册规范化，增加质量校验。

| 步骤 | 内容 | 涉及文件 | 风险 |
|---|---|---|---|
| 3.1 | 定义 `BaseExecutor` + `ExecutorRegistry` | `backend/app/gateway/executors/registry.py` | 低（与 CapabilityRegistry 共存） |
| 3.2 | 逐个迁移 Worker → Executor | `sql_executor.py`, `pdf_executor.py`, ... | 低 |
| 3.3 | 启用声明式注册（装饰器 / 文件扫描） | `executors/__init__.py` | 低 |
| 3.4 | 定义 `ValidationEngine` + 内置 Validator | `backend/app/gateway/runtime/validation_engine.py` | 低 |
| 3.5 | 在 Pipeline 中集成 Validation Layer | `report_pipeline.py` | 中 |
| 3.6 | 删除 `CapabilityRegistry` + `BaseWorker` | 清理 | 低 |

### 回滚策略

每个 Phase 的修改都保持向后兼容：

- Phase 1：`build_run_create_request` 函数签名不变，只重构内部实现
- Phase 2：`_detect_report_intent` 保留，KeywordIntentClassifier 作为其封装
- Phase 3：CapabilityRegistry 在 ExecutorRegistry 上线后保留一个 GC 周期

---

## 7. 文件变更清单

### 新增文件

| 文件 | 职责 | Phase |
|---|---|---|
| `backend/app/gateway/services_v1/context_builder.py` | ContextBuilder + 所有 Context 组件 | 1 |
| `backend/app/gateway/routing/__init__.py` | 路由模块 | 2 |
| `backend/app/gateway/routing/intent_classifier.py` | IntentClassifier 接口 + 实现 | 2 |
| `backend/app/gateway/routing/router.py` | 路由调度逻辑 | 2 |
| `backend/app/gateway/executors/__init__.py` | 执行器模块 + 自动发现 | 3 |
| `backend/app/gateway/executors/registry.py` | ExecutorRegistry | 3 |
| `backend/app/gateway/executors/base.py` | BaseExecutor | 3 |
| `backend/app/gateway/runtime/validation_engine.py` | ValidationEngine + 内置 Validator | 3 |

### 修改文件

| 文件 | 变更 | Phase |
|---|---|---|
| `run_adapter.py` | `build_run_create_request` 保留签名，内部委托给 ContextBuilder | 1 |
| `report_pipeline.py` | 集成 Validation Layer + ExecutorRegistry | 3 |
| `report_tool.py` | 移除 Runtime 上下文提取逻辑（由 ContextBuilder 完成） | 1 |
| `execution_runtime.py` | 适配 BaseExecutor（兼容 BaseWorker） | 3 |

### 删除文件（Phase 3 完成后）

| 文件 | 替代 |
|---|---|
| `capability_registry.py` | `executor_registry.py` |
| `workers/base.py` (BaseWorker) | `executors/base.py` (BaseExecutor) |

---

## 附录 A：架构图对比

### V1 架构图

```
User → build_run_create_request → Lead Agent → generate_report Tool → ReportPipeline (6层)
                                                                        ├─ Layer 1: Planning
                                                                        ├─ Layer 2: Execution (硬编码 Worker)
                                                                        ├─ Layer 3: Evidence
                                                                        ├─ Layer 4: Analysis
                                                                        ├─ Layer 5: Composition
                                                                        └─ Layer 6: Rendering
```

### V2 架构图

```
User
  │
  ▼
ContextBuilder
  ├─ MetadataBuilder
  ├─ ModeConfigBuilder
  ├─ DatasourceInstructionBuilder
  ├─ DatasourceMessageBuilder
  ├─ IntentClassifierComponent
  └─ MessageAssembler
  │
  ▼
Intent Router (MultiLayerIntentClassifier)
  │
  ├─ CHAT ──────────────► ChatAgent
  │
  ├─ REPORT ────────────► WorkflowRuntime
  │                           │
  │                           ▼
  │                    ReportPipeline
  │                      ├─ Planning
  │                      ├─ Execution (ExecutorRegistry)
  │                      ├─ Validation Layer (NEW)
  │                      ├─ Evidence
  │                      ├─ Analysis
  │                      ├─ Composition
  │                      └─ Rendering
  │
  ├─ RESEARCH ──────────► DeepResearchPipeline
  │
  ├─ ANALYSIS ──────────► AnalysisPipeline
  │
  └─ SKILL ─────────────► SkillRuntime
```

---

## 附录 B：验证指标

| 维度 | V1 基线 | V2 目标 | 验证方式 |
|---|---|---|---|
| 意图识别延迟 | ~20ms (关键词) | ~20ms (关键词) / ~220ms (LLM) | APM 监控 |
| 意图识别准确率 | ~80% (关键词) | >95% (多层) | A/B 测试 |
| Context 构建耗时 | ~50ms | ~30ms (并行构建) | 单元测试 |
| 新增 Executor 行数 | 修改 Pipeline + Registry | 仅新增 1 个文件 | 代码审查 |
| 数据质量事故 | 无校验 | 0% 脏数据进入 Composer | 集成测试 |
| 代码测试覆盖率 | 中 (集成测试为主) | 高 (组件级单元测试) | pytest --cov |
