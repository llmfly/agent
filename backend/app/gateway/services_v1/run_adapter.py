import logging
from dataclasses import dataclass
from typing import Any

from app.gateway.routers.thread_runs import RunCreateRequest
from app.gateway.schemas.v1.conversations import ConversationMessageRequest
from app.gateway.services_v1.external_context import ExternalContext, build_external_metadata, inject_external_user

logger = logging.getLogger(__name__)

# ── Report instruction blocks (injected into Lead Agent system prompt) ──────

@dataclass
class _IntentResult:
    is_report: bool = False
    decision: str = "general_chat"
    confidence: float = 0.0


def _detect_report_intent(content: str) -> _IntentResult:
    """Quick pre-routing check before the Lead Agent sees the message.

    Uses keyword detection (not LLM) for speed. If report intent is
    detected, the pipeline can bypass the Lead Agent entirely.
    """
    msg = content.lower()
    report_kw = [
        "生成报告", "分析报告", "出报告", "导出文档", "做一份报告", "生成文档",
        "解析文档", "总结文档", "分析文档", "文档总结", "总结汇报",
        "给出报告",
    ]
    for kw in report_kw:
        if kw in msg:
            return _IntentResult(is_report=True, decision="generate_report", confidence=0.9)
    return _IntentResult(is_report=False, decision="general_chat", confidence=0.0)


_NO_SOURCE_INSTRUCTIONS = """<system_instructions>
## 数据真实性规则（必须遵守）
⚠️ **所有结论、数据、分析结果必须完全来源于上传的文档内容。**
- 禁止捏造、虚构、编造任何数据、统计数字或事实
- 如果文档中没有某项数据，**必须明确告知用户「以下数据不在当前文档中」**
- 禁止根据常识或外部知识补充文档缺失的数据
- 引用的每条信息必须标注来源的文档名称

## 报告生成规则（必须遵守）
当用户要求「生成报告」「解析文档生成报告」「分析文档并出报告」「导出为文档」时，
**必须调用 `generate_report` 工具**，不得使用其他替代方案。

### generate_report 的使用方法
- **有数据源时**: generate_report(title="报告标题", user_query="分析需求描述")
- **有上传的文档时**: generate_report(title="报告标题", document_path="/mnt/user-data/uploads/文件名")
  document_path 参数指向已上传的 PDF/DOCX 文件路径

工具会全自动完成六层流程：Planning → Execution (Worker) → Evidence → Analysis → Composition → Rendering
- **文档解析由六层内部的 PdfWorker/DocxWorker 自动处理**
- **禁止先调 parse_pdf/parse_docx 再传 parse 结果给 generate_report**
- **禁止先调 parse_pdf/parse_docx 再自己在对话里输出解析内容**

### generate_report 成功后的行为（必须遵守）
一旦 `generate_report` 返回成功结果，必须立即结束，**禁止**：

- ❌ **禁止再次调用 `generate_report`** — 哪怕用户还有另一个人的报告需求
- ❌ **禁止调用 `check_report_status`** — 结果已返回，不需要再查
- ❌ **禁止使用 bash/Python 搜索、读取、操作报告文件**
- ❌ **禁止调用 `parse_pdf` / `parse_docx` / `query_data_source` 等任何其他工具**
- ❌ **禁止尝试在沙箱或服务器上寻找报告文件**

✅ **唯一允许的行为**：直接将工具返回的结果呈现给用户。

### generate_report 失败后的行为（必须遵守）
- 如果 `generate_report` 返回失败结果，**最多重试1次**（修改参数后）
- 如果仍然失败，**告诉用户失败原因，不要继续尝试其他方式生成报告**
- **禁止**使用 bash/Python 脚本生成 Word/HTML 文档作为替代

### 禁止行为
- ❌ **禁止调用 `parse_pdf` / `parse_docx`**——generate_report 内部自动解析文档
- ❌ 禁止用 bash 或 Python 脚本生成 Word 文档——generate_report 会自动渲染
- ❌ 禁止在对话中输出大量 Markdown 格式的报告内容
- ❌ 如果 generate_report 第一次失败，最多重试1次；仍失败就告诉用户
- ❌ **禁止虚构文档中不存在的数据**

违反以上规则将导致流程错误。
</system_instructions>"""


def _context_from_options(body: ConversationMessageRequest) -> dict[str, Any]:
    options = body.options
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
    return context


def _format_data_sources_for_prompt(ds_list: list[dict[str, Any]]) -> str:
    """Format data sources into an XML block with workflow guidance for the LLM.

    Includes structured schema_summary (table/column metadata, document overview)
    so the agent and downstream pipeline (e.g. ReportPlanner) understand exactly
    what data is available without needing to probe the source.
    """
    lines = [
        "<system_instructions>",
        "当前对话已关联以下数据源。",
        "",
        "## 数据真实性规则（必须遵守）",
        "⚠️ **所有结论、数据、分析结果必须完全来源于以下指定的数据源和已上传的文件。**",
        "- 禁止捏造、虚构、编造任何数据、统计数字或事实",
        "- 如果数据源中没有某项数据，**必须明确告知用户「以下数据不在当前数据源中」**",
        "- 禁止根据常识或外部知识补充数据源的缺失数据",
        "- 引用的每条数据必须标注来源的数据源名称或文件名称",
        "",
        "## 报告生成规则（必须遵守）",
        "当用户要求「生成报告」「分析数据并出报告」「解析文档生成报告」「导出为文档」时，",
        "**必须调用 `generate_report` 工具**，不得使用其他替代方案。",
        "",
        "### generate_report 的使用方法",
        "- **有 SQL 数据源时**: generate_report(title=\"报告标题\", user_query=\"分析需求描述\")",
        "  工具会全自动完成数据查询、分析、DOCX 渲染全流程",
        "- **有上传的文档时**: generate_report(title=\"报告标题\", document_path=\"/mnt/user-data/uploads/文件名\")",
        "  **禁止先调 parse_pdf/parse_docx**——generate_report 内部自动解析",
        "- **同时有数据源和文档时**: 两个参数都传",
        "",
        "工具会全自动完成六层流程：Planning → Execution (Worker) → Evidence → Analysis → Composition → Rendering",
        "",
        "### 禁止行为",
        "- ❌ 禁止使用 query_data_source 手动查询数据——generate_report 会自动查询",
        "- ❌ **禁止调用 `parse_pdf` / `parse_docx`**——generate_report 内部自动解析文档",
        "- ❌ 禁止用 bash 或 Python 脚本生成 Word 文档——generate_report 会自动渲染",
        "- ❌ 禁止在对话中输出大量 Markdown 格式的报告内容",
        "- ❌ 如果 generate_report 第一次失败，最多重试1次；仍失败就告诉用户，不要切到手动方案",
        "- ❌ **禁止虚构数据源中不存在的数据**",
        "",
        "违反以上规则将导致流程错误。",
        "</system_instructions>",
        "",
        "<data_sources>",
    ]
    for ds in ds_list:
        ds_id = ds.get("datasource_id", "?")
        ds_type = ds.get("type", "?")
        ds_name = ds.get("name", "?")
        meta = ds.get("metadata") or {}
        schema_summary = ds.get("schema_summary") or {}

        lines.append(f'  <datasource id="{ds_id}" type="{ds_type}" name="{ds_name}">')

        # ── Connection info for SQL types ────────────────────────
        if ds_type in ("sql", "mysql", "postgresql"):
            host = meta.get("host", "?")
            port = meta.get("port", "?")
            database = meta.get("database", "?")
            lines.append(f"    <connection>mysql://{host}:{port}/{database}</connection>")

        # ── Schema detail (table structures for SQL) ──────────────
        tables = schema_summary.get("tables", [])
        if tables:
            lines.append("    <schema>")
            for t in tables:
                tname = t.get("name", "?")
                rows = t.get("row_count", "?")
                lines.append(f'      <table name="{tname}" rows="{rows}">')
                for col in t.get("columns", []):
                    cname = col.get("name", "")
                    ctype = col.get("type", "")
                    pk = ' pk="true"' if col.get("pk") else ""
                    lines.append(f'        <column name="{cname}" type="{ctype}"{pk}/>')
                lines.append("      </table>")
            lines.append("    </schema>")

        # ── Document summary for file types ──────────────────────
        doc_summary = schema_summary.get("document_summary")
        if doc_summary:
            chapters = doc_summary.get("chapters") or doc_summary.get("key_topics") or []
            lines.append(f"    <document type=\"{doc_summary.get('type', ds_type)}\""
                         f" filename=\"{doc_summary.get('filename', '')}\">")
            if chapters:
                lines.append(f"      <topics>{', '.join(chapters)}</topics>")
            lines.append("    </document>")

        # ── Status note when extraction is still pending ──────────
        status = schema_summary.get("status", "pending")
        if status == "pending":
            lines.append("    <note>数据源元数据正在提取中，稍后即可使用</note>")
        elif status == "error":
            err_msg = schema_summary.get("error", "unknown error")
            lines.append(f"    <note>数据源元数据提取失败: {err_msg}</note>")

        lines.append("  </datasource>")

    lines.append("</data_sources>")
    return "\n".join(lines)


def build_run_create_request(
    body: ConversationMessageRequest,
    external_context: ExternalContext,
    *,
    selected_data_sources: list[dict[str, Any]] | None = None,
) -> RunCreateRequest:
    metadata = build_external_metadata(external_context, body.metadata)
    if body.datasource_ids:
        metadata["datasource_ids"] = list(body.datasource_ids)
    if selected_data_sources:
        metadata["selected_data_sources"] = selected_data_sources

    context = inject_external_user(_context_from_options(body), external_context)

    user_content = body.content
    has_sources = bool(selected_data_sources)

    # ── Pre-routing: check if user wants a report ──────────────────
    # This runs BEFORE the Lead Agent sees the message, acting as a
    # true Intent Layer. If the intent is "generate report", we route
    # directly to the pipeline instead of letting the LLM decide.
    intent = _detect_report_intent(user_content)
    if intent.is_report:
        logger.info(
            "Pre-routing: report intent detected (decision=%s, confidence=%.2f), "
            "bypassing Lead Agent",
            intent.decision, intent.confidence,
        )
        # Mark the context so downstream knows this is a report request
        context["_report_intent"] = intent.decision
        context["_report_confidence"] = intent.confidence

    # Inject data source info / report instructions into the user message.
    if has_sources:
        context["selected_data_sources"] = selected_data_sources
        ds_block = _format_data_sources_for_prompt(selected_data_sources)
        user_content = f"{ds_block}\n\n{body.content}"
        logger.info("build_run_create_request: injected %d data sources into prompt", len(selected_data_sources))
    else:
        # Still inject report-generation instructions so the Lead Agent
        # knows to use generate_report even without SQL datasources
        # (e.g. document-based reports).
        instructions = _NO_SOURCE_INSTRUCTIONS
        user_content = "{}\n\n{}".format(instructions, body.content)
        logger.info("build_run_create_request: injected report instructions (no datasources)")

    return RunCreateRequest(
        assistant_id=body.agent_id,
        input={"messages": [{"type": "human", "content": [{"type": "text", "text": user_content}]}]},
        metadata=metadata,
        context=context,
        stream_mode=["messages-tuple", "values", "updates", "custom", "events"],
        stream_subgraphs=True,
        stream_resumable=True,
        on_disconnect="cancel",
    )
