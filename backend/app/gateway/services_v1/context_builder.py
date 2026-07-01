"""ContextBuilder — modular context construction for run requests.

Replaces the monolithic ``build_run_create_request`` with a
responsibility-chain pattern.  Each ``ContextBuilderComponent``
handles one dimension of context construction.

Usage
-----
    builder = ContextBuilder()
    run_request = builder.build(body, context, selected_data_sources=[...])

This is the Phase-1 entrypoint.  ``run_adapter.build_run_create_request``
delegates to it internally for backward compatibility.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.gateway.routers.thread_runs import RunCreateRequest
from app.gateway.schemas.v1.conversations import ConversationMessageRequest
from app.gateway.services_v1.external_context import ExternalContext, build_external_metadata, inject_external_user

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  BuildContext — intermediate result passed through the component chain
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class BuildContext:
    """Accumulated context built by the component chain.

    Each component reads existing fields and writes its own output.
    Components are called sequentially; order matters.
    """

    # ── Raw inputs ────────────────────────────────────────────────
    body: ConversationMessageRequest
    external_context: ExternalContext
    selected_data_sources: list[dict[str, Any]] | None = None

    # ── Built artifacts ───────────────────────────────────────────
    metadata: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    messages: list[dict] = field(default_factory=list)

    # ── Intent detection result ───────────────────────────────────
    intent_decision: str = ""
    intent_confidence: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════
#  Component interface
# ═══════════════════════════════════════════════════════════════════════════


class ContextBuilderComponent(ABC):
    """Single-responsibility context builder.

    Each component handles exactly one dimension of the build process.
    Mutates the shared ``BuildContext`` and returns it.
    """

    @abstractmethod
    def build(self, ctx: BuildContext) -> BuildContext:
        ...


# ═══════════════════════════════════════════════════════════════════════════
#  Component 1: Metadata
# ═══════════════════════════════════════════════════════════════════════════


class MetadataBuilder(ContextBuilderComponent):
    """Build run metadata from external context + body metadata + data sources."""

    def build(self, ctx: BuildContext) -> BuildContext:
        ctx.metadata = build_external_metadata(ctx.external_context, ctx.body.metadata)
        if ctx.body.datasource_ids:
            ctx.metadata["datasource_ids"] = list(ctx.body.datasource_ids)
        if ctx.selected_data_sources:
            ctx.metadata["selected_data_sources"] = ctx.selected_data_sources
        return ctx


# ═══════════════════════════════════════════════════════════════════════════
#  Component 2: Mode / Options config
# ═══════════════════════════════════════════════════════════════════════════


class ModeConfigBuilder(ContextBuilderComponent):
    """Parse run options (mode, model, thinking, subagent, etc.) into context."""

    def build(self, ctx: BuildContext) -> BuildContext:
        options = ctx.body.options
        context: dict[str, Any] = {}
        mode = options.mode or "flash"
        context["mode"] = mode
        if options.model is not None:
            context["model_name"] = options.model
        if options.thinking_enabled is not None:
            context["thinking_enabled"] = options.thinking_enabled
        else:
            context["thinking_enabled"] = mode != "flash"
        if options.reasoning_effort is not None:
            context["reasoning_effort"] = options.reasoning_effort
        elif mode == "ultra":
            context["reasoning_effort"] = "high"
        elif mode == "pro":
            context["reasoning_effort"] = "medium"
        elif mode == "thinking":
            context["reasoning_effort"] = "low"
        if mode in {"pro", "ultra"}:
            context["is_plan_mode"] = True
        if options.subagent_enabled is not None:
            context["subagent_enabled"] = options.subagent_enabled
        elif mode == "ultra":
            context["subagent_enabled"] = True
        if options.max_concurrent_subagents is not None:
            context["max_concurrent_subagents"] = options.max_concurrent_subagents
        if options.citation_required is not None:
            context["citation_required"] = options.citation_required
        if options.max_context_tokens is not None:
            context["max_context_tokens"] = options.max_context_tokens
        ctx.context = inject_external_user(context, ctx.external_context)
        return ctx


# ═══════════════════════════════════════════════════════════════════════════
#  Component 3: Intent classification
# ═══════════════════════════════════════════════════════════════════════════


class IntentClassifierComponent(ContextBuilderComponent):
    """Detect report intent and set context flags for routing.

    Phase 1: Keyword-based matching on the original user message
             (before instruction prepending).  Equivalent to V1's
             ``_detect_report_intent``.
    """

    def build(self, ctx: BuildContext) -> BuildContext:
        from app.gateway.routing.intent_classifier import MultiLayerIntentClassifier

        classifier = MultiLayerIntentClassifier()
        result = classifier.classify(ctx.body.content, context=ctx.context)

        if result.confidence >= 0.9:
            ctx.intent_decision = result.intent.value
            ctx.intent_confidence = result.confidence
            logger.info(
                "IntentClassifier: %s detected (confidence=%.2f, reason=%s)",
                ctx.intent_decision, ctx.intent_confidence, result.reason,
            )
            ctx.context["_report_intent"] = ctx.intent_decision
            ctx.context["_report_confidence"] = ctx.intent_confidence
        else:
            ctx.intent_decision = "general_chat"
            ctx.intent_confidence = 0.0
        return ctx


# ═══════════════════════════════════════════════════════════════════════════
#  Component 4: Data source instructions (Few-shot)
# ═══════════════════════════════════════════════════════════════════════════


_NO_SOURCE_INSTRUCTIONS = """<system_instructions>
当前对话未关联数据源。

## 数据真实性规则
如果用户上传了文档，所有分析结果必须完全来源于文档内容，禁止捏造数据。

## ⚠️ 核心规则：用户要求出报告时，直接调 generate_report，禁止先做其他操作

当用户明确要求「生成报告」「解析文档」「导出报告」时：
**必须且仅能调用 `generate_report`，不得先做任何其他操作。**

❌ 禁止先翻文件系统目录
❌ 禁止先调用其他工具

## Examples — 什么时候该调用 generate_report

### ✅ 正例 1：用户上传了文档，要求解析出报告

User: 我上传了一份 PDF，帮我解析并生成报告
Assistant:
<function=generate_report>
{{"title": "文档分析报告"}}
</function>

### ✅ 正例 2：用户要求导出分析结果为文档

User: 把刚才的分析整理成报告导出
Assistant:
<function=generate_report>
{{"title": "分析报告", "user_query": "把之前的分析整理成报告导出"}}
</function>

### ❌ 反例 1：没有文档，用户只是要求分析

User: 帮我分析一下当前情况
Assistant: 当前没有关联数据源，请先上传文件或配置数据源。
（不需要调 generate_report，因为没有数据）

### ❌ 反例 2：闲聊

User: 你好
Assistant: 你好！有什么可以帮你的？
（不需要调用任何工具）

## 补充说明
- generate_report 内部自动解析文档和渲染
- 禁止先调 parse_pdf/parse_docx 再自己拼接
- generate_report 成功后立即结束，禁止再调其他工具
</system_instructions>"""


def _format_data_sources_for_prompt(ds_list: list[dict[str, Any]]) -> str:
    """Format Few-shot examples about data sources and report generation.

    Uses examples (正例 + 反例) instead of verbose rules. The LLM learns
    the pattern naturally — when to call ``generate_report`` vs when to
    just chat.
    """
    sql_count = sum(1 for ds in ds_list if ds.get("type") in ("sql", "mysql", "postgresql"))
    file_count = sum(1 for ds in ds_list if ds.get("type") in ("pdf", "docx", "txt", "xlsx", "csv"))
    parts = []
    if sql_count:
        parts.append(f"{sql_count} 个 SQL 数据库")
    if file_count:
        parts.append(f"{file_count} 个文档文件")
    summary = "、".join(parts) if parts else f"{len(ds_list)} 个数据源"

    return f"""<system_instructions>
当前对话已关联 {summary}。

**注意：以下词语都指代当前已绑定的数据源，不要要求用户重新上传或指定路径：**
「文档」「文件」「PDF」「Word」「数据」「数据库」「上传的数据」「资料」「分析」
当用户说"依据文档""根据文件""分析数据""结合数据源"时，**默认就是指下方 <datasources> 中已绑定的数据源**。

## 数据真实性规则
所有结论、数据、分析结果必须完全来源于以下指定的数据源和已上传的文件。禁止捏造数据。

## ⚠️ 核心规则：用户要求出报告时，直接调 generate_report，禁止先做其他操作

当用户明确要求「生成报告」「解析数据」「解析文档」「分析数据并出报告」时：
**必须且仅能调用 `generate_report`，不得先做任何其他操作。**

❌ 禁止先翻文件系统目录（ls /mnt/user-data/ 等）
❌ 禁止先调 query_data_source 查询数据源结构
❌ 禁止先调 parse_pdf / parse_docx
❌ 禁止先搜索文件

generate_report 内部会自动查询数据、解析文档、分析、排版、渲染。
**调用前不需要做任何准备工作。**

## Examples — 什么时候该调用 generate_report（数据源由工具自动解析，不需要传路径）

### ✅ 正例 1：SQL 数据源分析出报告

User: 帮我分析出口数据
Assistant:
<function=generate_report>
{{"title": "出口数据分析报告", "user_query": "分析出口数据"}}
</function>

### ✅ 正例 2：已上传文档，解析并出报告

User: 解析文档，给出报告
Assistant:
<function=generate_report>
{{"title": "文档分析报告", "user_query": "解析文档内容，给出分析报告"}}
</function>

### ✅ 正例 3：同时有 SQL 和文档数据源

User: 结合两个数据源，给我一份对比分析报告
Assistant:
<function=generate_report>
{{"title": "综合对比分析报告", "user_query": "结合两个数据源做对比分析报告"}}
</function>

### ✅ 正例 4：已经出过报告，用户要求重新生成或调整

User: 报告里数据分析不够深入，重新出一份，重点分析趋势
Assistant:
<function=generate_report>
{{"title": "出口数据趋势分析报告（修订版）", "user_query": "重点分析出口数据趋势"}}
</function>

### ✅ 正例 5：直接说分析数据给报告

User: 解析数据，给出报告
Assistant:
<function=generate_report>
{{"title": "数据分析报告", "user_query": "解析当前所有数据源，给出分析报告"}}
</function>

### ❌ 反例 1：用户只是问问题，不需要出报告

User: 最近出口数据怎么样，有什么异常
Assistant: 我来查一下数据。[调用 query_data_source 或其他工具查询]
（不需要调用 generate_report，除非用户明确要求出报告文档）

### ❌ 反例 2：查看数据源有哪些

User: 当前关联了哪些数据源
Assistant: 我来查一下。[调用 query_data_source]
（不需要调用 generate_report）

### ❌ 反例 3：闲聊或无关话题

User: 你好，你是谁
Assistant: 你好！我是 DeerFlow 助手...
（不需要调用任何工具）

## 补充说明
- generate_report 内部自动解析文档、执行 SQL 查询、分析、排版和渲染，**调用时不需要传任何文件路径**
- 禁止先调 parse_pdf/parse_docx，再自己拼接内容——generate_report 全自动处理
- 如果 generate_report 失败，最多重试 1 次（调整参数），仍失败则告知用户原因
- generate_report 成功后立即结束，禁止再调任何其他工具或搜索文件系统
</system_instructions>"""


def _build_datasource_system_message(ds_list: list[dict[str, Any]]) -> str:
    """Build a compact system message describing the current data sources.

    This is injected as a separate system message (not in the user message
    prefix) so it only needs to be updated when data sources change, saving
    tokens on normal turns.
    """
    lines = ["<datasources>"]
    for ds in ds_list:
        ds_id = ds.get("datasource_id", "?")
        ds_type = ds.get("type", "?")
        ds_name = ds.get("name", "?")
        meta = ds.get("metadata") or {}
        ss = ds.get("schema_summary") or {}

        lines.append(f'  <datasource id="{ds_id}" type="{ds_type}" name="{ds_name}">')

        # SQL types: table names + row counts
        if ds_type in ("sql", "mysql", "postgresql"):
            host = meta.get("host", "?")
            port = meta.get("port", "?")
            database = meta.get("database", "?")
            lines.append(f"    <connection>{host}:{port}/{database}</connection>")
            tables = ss.get("tables", [])
            if tables:
                for t in tables:
                    tname = t.get("name", "?")
                    rows = t.get("row_count", "?")
                    cols = ", ".join(
                        f"{c['name']}({c['type']})"
                        for c in t.get("columns", [])[:6]
                    )
                    lines.append(f"    <table name=\"{tname}\" rows=\"{rows}\" columns=\"{cols}\"/>")

        # File types: path + preview
        if ds_type in ("pdf", "docx", "txt", "xlsx", "csv"):
            file_path = meta.get("file_path", "")
            if file_path:
                lines.append(f"    <file_path>{file_path}</file_path>")
            doc_summary = ss.get("document_summary")
            if doc_summary:
                pages = doc_summary.get("page_count", "?")
                preview = doc_summary.get("content_preview", "")[:300]
                chapters = doc_summary.get("chapters") or doc_summary.get("key_topics") or []
                if chapters:
                    lines.append(f"    <topics>{', '.join(chapters)}</topics>")
                lines.append(f"    <file pages=\"{pages}\"/>")

        lines.append("  </datasource>")

    lines.append("</datasources>")
    return "\n".join(lines)


class DatasourceInstructionBuilder(ContextBuilderComponent):
    """Prepend system instructions (Few-shot examples) to the user message.

    Equivalent to the instruction injection block in V1's
    ``build_run_create_request``.
    """

    def build(self, ctx: BuildContext) -> BuildContext:
        if ctx.selected_data_sources:
            ctx.context["selected_data_sources"] = ctx.selected_data_sources
            instructions = _format_data_sources_for_prompt(ctx.selected_data_sources)
            logger.info(
                "DatasourceInstructionBuilder: %d data sources for prompt",
                len(ctx.selected_data_sources),
            )
        else:
            instructions = _NO_SOURCE_INSTRUCTIONS
            logger.info("DatasourceInstructionBuilder: injected report instructions (no datasources)")

        ctx.body.content = f"{instructions}\n\n{ctx.body.content}"
        return ctx


# ═══════════════════════════════════════════════════════════════════════════
#  Component 5: Datasource system message (XML schema)
# ═══════════════════════════════════════════════════════════════════════════


class DatasourceMessageBuilder(ContextBuilderComponent):
    """Append datasource detail system message (XML schema snapshot).

    Only emits a system message when data sources are present.
    """

    def build(self, ctx: BuildContext) -> BuildContext:
        if ctx.selected_data_sources:
            ds_system_msg = _build_datasource_system_message(ctx.selected_data_sources)
            ctx.messages.append({
                "type": "system",
                "content": [{"type": "text", "text": ds_system_msg}],
            })
        return ctx


# ═══════════════════════════════════════════════════════════════════════════
#  Component 6: Message assembler
# ═══════════════════════════════════════════════════════════════════════════


class MessageAssembler(ContextBuilderComponent):
    """Append the human message (with prepended instructions) to the messages list."""

    def build(self, ctx: BuildContext) -> BuildContext:
        ctx.messages.append({
            "type": "human",
            "content": [{"type": "text", "text": ctx.body.content}],
        })
        return ctx


# ═══════════════════════════════════════════════════════════════════════════
#  Orchestrator
# ═══════════════════════════════════════════════════════════════════════════


class ContextBuilder:
    """Orchestrates the context building responsibility chain.

    Each component is called in order.  The chain is fixed at construction
    time — to add a new context dimension, create a new component and insert
    it via a subclass or factory method.

    Usage
    -----
        builder = ContextBuilder()
        run_request = builder.build(body, context, selected_data_sources=[...])
    """

    def __init__(self, components: list[ContextBuilderComponent] | None = None) -> None:
        self._components = components or self._default_components()

    @staticmethod
    def _default_components() -> list[ContextBuilderComponent]:
        """Default chain — order is significant.

        1. Metadata            — external context + metadata
        2. Mode config         — options → context dict
        3. Intent classify     — detect intent ON ORIGINAL message (before modification)
        4. Datasource instr    — prepend Few-shot instructions to user message
        5. Datasource message  — append datasource XML system message
        6. Message assembler   — append human message
        """
        return [
            MetadataBuilder(),
            ModeConfigBuilder(),
            IntentClassifierComponent(),
            DatasourceInstructionBuilder(),
            DatasourceMessageBuilder(),
            MessageAssembler(),
        ]

    def build(
        self,
        body: ConversationMessageRequest,
        external_context: ExternalContext,
        *,
        selected_data_sources: list[dict[str, Any]] | None = None,
    ) -> RunCreateRequest:
        """Build a complete ``RunCreateRequest``.

        Args:
            body: The incoming conversation message request.
            external_context: Auth / external user context.
            selected_data_sources: Optional list of attached data source schemas.

        Returns:
            A ``RunCreateRequest`` ready for submission.
        """
        ctx = BuildContext(
            body=body,
            external_context=external_context,
            selected_data_sources=selected_data_sources,
        )
        for component in self._components:
            ctx = component.build(ctx)

        return RunCreateRequest(
            assistant_id=body.agent_id,
            input={"messages": ctx.messages},
            metadata=ctx.metadata,
            context=ctx.context,
            stream_mode=["messages-tuple", "values", "updates", "custom", "events"],
            stream_subgraphs=True,
            stream_resumable=True,
            on_disconnect="cancel",
        )
