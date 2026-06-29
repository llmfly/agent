"""Report generation tool — triggers the 7-layer report pipeline.

Entry point: one tool call → full 7-layer pipeline does everything.
Returns ``Command(goto=END)`` to force-stop the agent graph after completion."""

from __future__ import annotations

import logging
import os
from typing import Annotated, Any

from langchain.tools import InjectedToolCallId, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from deerflow.tools.types import Runtime

from app.gateway.runtime.report_pipeline import ReportPipeline

logger = logging.getLogger(__name__)


def _get_thread_id(runtime: Runtime) -> str | None:
    thread_id = runtime.context.get("thread_id") if runtime.context else None
    if thread_id:
        return thread_id
    cfg = getattr(runtime, "config", None) or {}
    thread_id = cfg.get("configurable", {}).get("thread_id")
    if thread_id:
        return thread_id
    try:
        from langgraph.config import get_config
        return get_config().get("configurable", {}).get("thread_id")
    except RuntimeError:
        return None


def _get_sql_sources(runtime: Runtime) -> list[dict]:
    selected_sources = None
    if runtime.context:
        selected_sources = runtime.context.get("selected_data_sources")
    if not selected_sources:
        cfg = getattr(runtime, "config", None) or {}
        selected_sources = (
            cfg.get("configurable", {}).get("selected_data_sources")
            or cfg.get("context", {}).get("selected_data_sources")
        )
    if not selected_sources:
        return []
    return [ds for ds in selected_sources if ds.get("type") == "sql"]


def _get_schema_summary(runtime: Runtime) -> dict[str, Any]:
    """Extract schema_summary from the first SQL data source (if any)."""
    selected_sources = None
    if runtime.context:
        selected_sources = runtime.context.get("selected_data_sources")
    if not selected_sources:
        cfg = getattr(runtime, "config", None) or {}
        selected_sources = (
            cfg.get("configurable", {}).get("selected_data_sources")
            or cfg.get("context", {}).get("selected_data_sources")
        )
    if not selected_sources:
        return {}
    sql_sources = [ds for ds in selected_sources if ds.get("type") == "sql"]
    if not sql_sources:
        return {}
    ss = sql_sources[0].get("schema_summary") or {}
    return ss


def _get_server_base_url(runtime: Runtime) -> str:
    """Get the server base URL for constructing absolute download links.

    Priority:
    1. SERVER_BASE_URL env var (set in deploy config)
    2. runtime configurable
    3. Fallback to relative path
    """
    url = os.environ.get("SERVER_BASE_URL")
    if url:
        return url.rstrip("/")
    cfg = getattr(runtime, "config", None) or {}
    url = cfg.get("configurable", {}).get("server_base_url")
    if url:
        return url.rstrip("/")
    return ""


@tool(parse_docstring=True)
async def generate_report(
    title: str,
    runtime: Runtime,
    tool_call_id: Annotated[str, InjectedToolCallId],
    user_query: str = "",
    format: str = "docx",
    document_path: str = "",
) -> Command:
    """通过七层架构一键生成结构化分析报告。

    ⚠️ **何时必须调用此工具：**
    - 用户要求「生成报告」「分析数据并出报告」「导出为文档」「写一份报告」「出分析报告」等
    - 已经上传了文档（PDF/DOCX），需要基于文档生成报告 → **同时传入 `document_path`**

    ⚠️ **何时不使用此工具：**
    - 用户需求涉及 **「企业出海」「出海贸易」「出口贸易」「海关交易分析」「企业出海洞察」** → 应使用 **`company-insight-report` Skill**
    - 用户只是问问题、查询数据，不要求生成文档

    **使用方式：**
    - 如果已上传文档（PDF/DOCX），传入 `document_path`（如 `/mnt/user-data/uploads/file.pdf`）
    - 七层架构的 Layer 2 ExecutionRuntime 会自动调用 PdfWorker/DocxWorker 解析文件
    - 不需要先调 parse_pdf/parse_docx，Worker 会处理

    七层流程（全部 7 层都会执行）：
    Layer 1: Planning (生成计划) → ReportPlannerAgent (产生大纲 + 数据任务)
    Layer 2: Execution (执行数据任务) → ExecutionRuntime + Workers (SQL/Document)
    Layer 3: Evidence (聚合证据) → EvidenceAggregator
    Layer 4: Analysis (分析洞察) → AnalysisGraph
    Layer 5: Composition (撰写报告) → ReportComposerAgent
    Layer 6: Rendering (渲染输出) → DocxRenderer/HtmlRenderer
    Layer 7: Finalization (打包 + 摘要) → 构建结构化摘要，无需再读取文件

    Args:
        title: 报告标题。从用户对话中提取，例如"2024年出口贸易分析报告"。
        user_query: 用户的自然语言需求描述，例如"按目的国统计出口金额，按月度分析趋势"。如果不传会使用 title。
        format: 输出格式。可选值: docx, html。默认为 docx。
        document_path: 上传的文档路径（如 `/mnt/user-data/uploads/file.pdf`）。如有已上传的文档，**必须**传此参数。

    ⚠️ **重要：调用成功后的行为：**
    此工具返回结果后，**必须立即停止**，直接将结果呈现给用户。
    **禁止**再次调用 generate_report、check_report_status 或任何其他工具。
    **禁止**使用 bash/Python 搜索或操作报告文件。
    """
    conversation_id = _get_thread_id(runtime)
    logger.info("[generate_report] conversation=%s title=%s query=%s", conversation_id, title, user_query)

    if not conversation_id:
        return Command(
            update={
                "messages": [ToolMessage(
                    content="错误：无法获取当前对话 ID。",
                    tool_call_id=tool_call_id,
                    name="generate_report",
                )]
            },
        )

    sql_sources = _get_sql_sources(runtime)
    datasource_metadata = {}
    schema_summary: dict[str, Any] = {}
    if sql_sources:
        datasource_metadata = sql_sources[0].get("metadata") or {}
        schema_summary = sql_sources[0].get("schema_summary") or {}

    user_id = runtime.context.get("user_id", "anonymous") if runtime.context else "anonymous"

    pipeline = ReportPipeline()
    result = await pipeline.run(
        title=title,
        user_query=user_query or title,
        datasource_metadata=datasource_metadata,
        schema_summary=schema_summary,
        document_path=document_path,
        user_id=user_id,
        conversation_id=conversation_id,
        file_format=format,
    )

    if not result.success:
        return Command(
            update={
                "messages": [ToolMessage(
                    content=(
                        f"❌ 报告生成失败: {result.error}\n\n"
                        "⚠️ 本次生成已终止，请检查参数后重试。无需再次调用 generate_report，"
                        "除非用户明确要求重新生成。"
                    ),
                    tool_call_id=tool_call_id,
                    name="generate_report",
                )]
            },
        )

    # ── Construct absolute download URL with server IP ───────────────
    base_url = _get_server_base_url(runtime)
    if base_url:
        absolute_download_url = f"{base_url}{result.download_url}"
        download_line = f"   - 📥 **下载链接**: [点击下载]({absolute_download_url})"
    else:
        absolute_download_url = result.download_url
        download_line = f"   - 📥 **下载链接**: {absolute_download_url}"

    # ── Build the final message ──────────────────────────────────────
    parts = [
        result.final_summary,
        "",
        "---",
        f"### 📥 报告下载\n{download_line}",
        "",
        "---",
        "💡 **根据以上报告内容，用户可能想进一步了解：**",
        "  - 某个章节的具体数据细节",
        "  - 对报告中的发现进行深入分析",
        "  - 生成其他维度或视角的报告",
        "  - 导出为其他格式",
        "",
        "⚠️ **数据真实性规则**",
        "- 本报告中所有结论、数据、分析结果均已完全来源于用户指定的数据源和上传的文档。",
        "- 请直接使用以上 final_summary 内容回复用户，**禁止** 试图读取、解析、或验证报告文件。",
        "- 如果用户询问报告中未涉及的数据，请明确告知「该数据不在当前数据源中」。",
        "- **禁止** 凭常识或外部知识补充或编造报告中不存在的数据。",
    ]
    final_content = "\n".join(parts)

    # ═══════════════════════════════════════════════════════════════════
    # Force-stop: return Command(goto=END) so LangGraph routes to __end__
    # after this tool completes. The LLM will NOT get another turn.
    # ═══════════════════════════════════════════════════════════════════
    return Command(
        goto="__end__",
        update={
            "messages": [ToolMessage(
                content=final_content,
                tool_call_id=tool_call_id,
                name="generate_report",
            )]
        },
    )


@tool(parse_docstring=True)
async def check_report_status(
    report_id: str,
    runtime: Runtime,
) -> str:
    """查询报告生成状态和下载链接。

    Args:
        report_id: 报告 ID，格式为 art_xxx，来自 generate_report 的返回结果。
    """
    from app.gateway.services_v1.artifact_service import artifact_service
    art = await artifact_service.get_artifact(report_id)
    if art is None:
        return f"未找到报告 {report_id}。"
    return f"报告: {art.name}\n状态: {art.status}\n文件: {[f.filename for f in art.files]}\n"
