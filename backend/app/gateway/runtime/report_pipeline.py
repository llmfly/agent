"""ReportPipeline — 6-layer report generation orchestrator.

Intent routing is handled by the Lead Agent itself. The pipeline
starts directly from Planning:

  1. Planning Layer  → ReportPlannerAgent (Business DAG + Outline + Analysis Reqs)
  2. Execution Layer → ExecutionPlanner + ExecutionRuntime (DAG → Evidence)
  3. Evidence Layer  → EvidenceAggregator (dedup → graph)
  4. Analysis Layer  → AnalysisGraph (parallel analysis → Insights)
  5. Composition     → ReportComposerAgent (Outline + Insights → ReportSpec)
  6. Rendering       → DocxRenderer/HtmlRenderer (ReportSpec → bytes → artifact)

This replaces the old ReportWorkflow state machine.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deerflow.config.paths import get_paths

from app.gateway.agents.analysis_graph import AnalysisGraph, create_default_analysis_graph
from app.gateway.agents.report_composer import ReportComposerAgent
from app.gateway.agents.report_planner import ReportPlannerAgent
from app.gateway.models.evidence import EvidenceGraph
from app.gateway.planning.capability_registry import get_capability_registry
from app.gateway.planning.execution_planner import ExecutionPlanner
from app.gateway.planning.models import BusinessDAG, BusinessTask, ReportOutline, SectionDef
from app.gateway.runtime.evidence_aggregator import EvidenceAggregator
from app.gateway.runtime.execution_runtime import ExecutionRuntime
from app.gateway.schemas.v1.reports import ReportSpec
from app.gateway.workers.base import ExecutionDAG

logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────


def _fmt_duration(seconds: float) -> str:
    """Format duration for logging."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{seconds / 60:.1f}m"


# ── Data Classes ──────────────────────────────────────────────────────────


@dataclass
class PipelineResult:
    """Result of a full pipeline execution."""

    success: bool = False
    artifact_id: str = ""
    download_url: str = ""
    file_path: str = ""
    error: str | None = None

    # Intermediate outputs (for logging / response)
    title: str = ""
    outline_summary: str = ""
    evidence_count: int = 0
    insight_count: int = 0
    section_count: int = 0

    # Final structured summary (populated in Layer 7)
    # Contains section headings + content previews + follow-up questions
    # so the LLM never needs to read the report file.
    final_summary: str = ""


# ── Pipeline ──────────────────────────────────────────────────────────────


class ReportPipeline:
    """6-layer report generation pipeline.

    Usage:
        pipeline = ReportPipeline()
        result = await pipeline.run(
            title="分析报告",
            user_query="按国家统计2024年出口数据",
            datasource_metadata={...},
            user_id="...",
            conversation_id="...",
            file_format="docx",
        )
    """

    # Layer names for consistent logging
    LAYER_NAMES = [
        "Planning (生成计划)",
        "Execution (执行数据任务)",
        "Evidence (聚合证据)",
        "Analysis (分析洞察)",
        "Composition (撰写报告)",
        "Rendering (渲染输出)",
        "Finalization (打包最终结果)",
    ]

    def __init__(self) -> None:
        self._report_planner = ReportPlannerAgent()
        self._analysis_graph = create_default_analysis_graph()
        self._report_composer = ReportComposerAgent()
        self._evidence_aggregator = EvidenceAggregator()
        self._start_time: float = 0.0
        self._layer_times: list[float] = []

    def _log_layer(self, layer_num: int, message: str, *args: Any) -> None:
        """Log with consistent layer prefix."""
        name = self.LAYER_NAMES[layer_num - 1]
        elapsed = time.time() - self._start_time
        logger.info(
            "[Pipeline] Layer %d/7 ▸ %s  [%s]  %s",
            layer_num, name, _fmt_duration(elapsed), message % args,
        )

    def _log_layer_result(self, layer_num: int, detail: str) -> None:
        elapsed = time.time() - self._start_time
        logger.info(
            "[Pipeline]   ✔ Layer %d done [%s] — %s",
            layer_num, _fmt_duration(elapsed), detail,
        )

    async def run(
        self,
        *,
        title: str,
        user_query: str,
        datasource_metadata: dict[str, Any],
        schema_summary: dict[str, Any] | None = None,
        document_path: str = "",
        user_id: str = "anonymous",
        conversation_id: str = "",
        file_format: str = "docx",
    ) -> PipelineResult:
        """Execute the 7-layer report generation pipeline.

        The Lead Agent has already confirmed report intent before calling
        this pipeline. Each layer is fail-fast: if a layer produces no
        output, the pipeline stops immediately and returns the error.

        Layers:
        1. Planning     — 生成报告大纲和数据任务
        2. Execution    — 执行数据收集任务
        3. Evidence     — 聚合和去重证据
        4. Analysis     — 分析洞察
        5. Composition  — 撰写报告内容
        6. Rendering    — 渲染为 DOCX/HTML
        7. Finalization — 打包最终结果

        Args:
            title: Report title.
            user_query: User's natural language query.
            datasource_metadata: Data source connection info (host, port, etc.).
            document_path: Sandbox virtual path to an uploaded document
                           (e.g. ``/mnt/user-data/uploads/file.pdf``).
            user_id: User ID for artifact storage.
            conversation_id: Thread/conversation ID.
            file_format: Output format (docx or html).

        Returns:
            PipelineResult with artifact info.
        """
        self._start_time = time.time()
        result = PipelineResult(title=title)
        logger.info("=" * 70)
        logger.info("[Pipeline] ╔══ 报告生成管道启动 ══╗")
        logger.info("[Pipeline]   query: %s", user_query[:120])
        logger.info("[Pipeline]   format: %s, conversation: %s", file_format, conversation_id[:12] if conversation_id else "N/A")
        if document_path:
            logger.info("[Pipeline]   document_path: %s", document_path)
        logger.info("=" * 70)

        try:
            # ════════════════════════════════════════════════════════════
            # Layer 1: Planning
            # ════════════════════════════════════════════════════════════
            self._log_layer(1, "生成报告计划")
            t0 = time.time()
            planner_output = await self._report_planner.plan(
                user_query,
                context={
                    "datasource_metadata": datasource_metadata,
                    "schema_summary": schema_summary or {},
                    "document_path": document_path,
                },
            )
            dt = time.time() - t0

            result.title = planner_output.title or title
            outline = planner_output.outline
            dag = planner_output.business_dag

            # If document_path is provided, inject a document_parse task
            # so Layer 3's ExecutionRuntime routes it to PdfWorker/DocxWorker
            if document_path and "document_parse" not in dag.tasks:
                from app.gateway.planning.models import BusinessTask
                doc_task = BusinessTask(
                    id="document_parse",
                    name="document_parse",
                    description="解析上传的文档内容",
                    input={"file_path": document_path, "max_pages": 0},
                    dependencies=[],
                )
                dag.add(doc_task)
                logger.info("[Pipeline]   Injected document_parse task: %s", document_path)

            section_details = ", ".join(
                f"{s.section_id}:{s.heading[:30]}" for s in outline.sections[:5]
            )
            task_details = ", ".join(f"{tid}:{dag.tasks[tid].name if tid in dag.tasks else tid}" for tid in list(dag.tasks.keys())[:5])

            logger.info("[Pipeline]   Plan LLM call took %s", _fmt_duration(dt))
            logger.info("[Pipeline]   Report title: %s", result.title)
            logger.info("[Pipeline]   Sections (%d): %s", len(outline.sections), section_details)
            logger.info("[Pipeline]   Task types (%d): %s", len(dag.tasks), task_details)
            logger.info("[Pipeline]   Required insight types: %s", outline.get_required_insight_types())
            if len(outline.sections) > 5:
                logger.info("[Pipeline]     ... plus %d more sections", len(outline.sections) - 5)
            if len(dag.tasks) > 5:
                logger.info("[Pipeline]     ... plus %d more tasks", len(dag.tasks) - 5)

            result.outline_summary = f"{len(outline.sections)} 章节, {len(dag.tasks)} 个数据任务"
            self._log_layer_result(1, f"标题={result.title}, {result.outline_summary}")

            # ── Fail-fast: Planning must produce sections ──
            if not outline.sections:
                raise RuntimeError(
                    "Layer 1 (Planning) 未能生成报告大纲，终止管道"
                )

            # ════════════════════════════════════════════════════════════
            # Layer 2: Execution
            # ════════════════════════════════════════════════════════════
            self._log_layer(2, "解析和执行数据任务")
            t0 = time.time()
            all_evidence = await self._execute_plan(dag, datasource_metadata, document_path)
            dt = time.time() - t0
            result.evidence_count = len(all_evidence)

            # Log evidence breakdown by type
            type_counts: dict[str, int] = {}
            for ev in all_evidence:
                t = getattr(ev, "type", "unknown") or "unknown"
                type_counts[t] = type_counts.get(t, 0) + 1
            type_summary = ", ".join(f"{k}={v}" for k, v in sorted(type_counts.items()))

            logger.info("[Pipeline]   Execution took %s", _fmt_duration(dt))
            logger.info("[Pipeline]   Evidence types: %s", type_summary or "empty")
            if result.evidence_count == 0:
                logger.warning("[Pipeline]   ⚠ 没有收集到任何证据数据")
            self._log_layer_result(2, f"获取了 {result.evidence_count} 条证据")

            # ── Fail-fast: no evidence from Execution layer ──
            if result.evidence_count == 0:
                article = "请检查输入数据或上传的文档是否有有效内容"
                raise RuntimeError(
                    f"Layer 2 (Execution) 未收集到任何证据，终止管道。{article}"
                )

            # ════════════════════════════════════════════════════════════
            # Layer 3: Evidence
            # ════════════════════════════════════════════════════════════
            self._log_layer(3, "聚合和去重证据")
            t0 = time.time()
            evidence_graph = self._evidence_aggregator.aggregate(all_evidence)
            dt = time.time() - t0

            source_types = evidence_graph.source_types
            logger.info("[Pipeline]   Aggregation took %s", _fmt_duration(dt))
            logger.info("[Pipeline]   Graph: total=%d, roots=%d, source_types=%s",
                        evidence_graph.total_count,
                        len(evidence_graph.root_ids),
                        source_types)
            self._log_layer_result(3, f"证据图 {evidence_graph.total_count} 节点")

            # ── Fail-fast: no evidence in graph ──
            if evidence_graph.total_count == 0:
                raise RuntimeError(
                    "Layer 3 (Evidence) 证据聚合后为空，终止管道"
                )

            # ════════════════════════════════════════════════════════════
            # Layer 4: Analysis
            # ════════════════════════════════════════════════════════════
            self._log_layer(4, "运行分析节点")
            analysis_context = {"user_query": user_query, "title": result.title}
            t0 = time.time()
            insights = await self._analysis_graph.run(evidence_graph, analysis_context)
            dt = time.time() - t0
            result.insight_count = len(insights)

            # Log insight breakdown by type
            insight_counts: dict[str, int] = {}
            for ins in insights:
                it = getattr(ins, "insight_type", "unknown") or "unknown"
                insight_counts[it] = insight_counts.get(it, 0) + 1
            insight_summary = ", ".join(f"{k}={v}" for k, v in sorted(insight_counts.items()))

            logger.info("[Pipeline]   Analysis took %s", _fmt_duration(dt))
            logger.info("[Pipeline]   Insights (%d): %s", len(insights), insight_summary)
            available_nodes = self._analysis_graph.list_types()
            logger.info("[Pipeline]   Analysis nodes available: %s", available_nodes)
            if result.insight_count == 0:
                logger.warning("[Pipeline]   ⚠ 分析节点未产生任何洞察")
            self._log_layer_result(4, f"{result.insight_count} 条洞察 ({insight_summary})")

            # ── Fail-fast: no insights ──
            if result.insight_count == 0:
                raise RuntimeError(
                    "Layer 4 (Analysis) 未产生任何洞察，终止管道"
                )

            # ════════════════════════════════════════════════════════════
            # Layer 5: Composition
            # ════════════════════════════════════════════════════════════
            self._log_layer(5, "撰写报告内容")
            t0 = time.time()
            report_spec = await self._report_composer.compose(
                outline,
                insights,
                title=result.title,
                subtitle=f"自动生成 | 基于 {result.evidence_count} 项数据",
                context={"user_query": user_query},
            )
            dt = time.time() - t0
            result.section_count = len(report_spec.sections)

            # Log section details
            content_stats = {
                "total_text_chars": sum(len(s.content) for s in report_spec.sections),
                "total_citations": len(report_spec.citations),
            }
            section_names = ", ".join(
                s.heading[:25] for s in report_spec.sections[:5]
            )
            logger.info("[Pipeline]   Composition took %s", _fmt_duration(dt))
            logger.info("[Pipeline]   Sections (%d): %s", len(report_spec.sections), section_names)
            logger.info("[Pipeline]   Content stats: text=%d chars, citations=%d",
                        content_stats["total_text_chars"], content_stats["total_citations"])
            if len(report_spec.sections) > 5:
                logger.info("[Pipeline]     ... plus %d more sections", len(report_spec.sections) - 5)
            self._log_layer_result(5, f"{result.section_count} 章节, {content_stats['total_text_chars']} 字符")

            # ── Fail-fast: Composition must produce sections ──
            if result.section_count == 0:
                raise RuntimeError(
                    "Layer 5 (Composition) 未生成任何章节内容，终止管道"
                )

            # ════════════════════════════════════════════════════════════
            # Layer 6: Rendering
            # ════════════════════════════════════════════════════════════
            self._log_layer(6, f"渲染为 {file_format}")
            t0 = time.time()
            artifact_id, download_url, file_path = await self._render_and_store(
                report_spec, result.title, user_id, conversation_id, file_format,
            )
            dt = time.time() - t0
            result.artifact_id = artifact_id
            result.download_url = download_url
            result.file_path = file_path
            result.success = True

            file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
            logger.info("[Pipeline]   Rendering took %s", _fmt_duration(dt))
            logger.info("[Pipeline]   File: %s (%s)", file_path, _fmt_duration(file_size) if file_size < 1024 else f"{file_size / 1024:.0f}KB")
            logger.info("[Pipeline]   Artifact: %s → %s", artifact_id, download_url)
            self._log_layer_result(6, f"文件大小={file_size} bytes")

            # ════════════════════════════════════════════════════════════
            # Layer 7: Finalization — build structured summary for LLM
            # ════════════════════════════════════════════════════════════
            self._log_layer(7, "打包最终结果")
            total_time = time.time() - self._start_time
            result.success = True

            # ── Build section summaries from report_spec ──────────────
            section_lines: list[str] = []
            for i, sec in enumerate(report_spec.sections, 1):
                # Extract content preview: first few text blocks
                preview_parts: list[str] = []
                for block in sec.content[:5]:
                    if block.text and block.text.strip():
                        text = block.text.strip()[:150]
                        preview_parts.append(text)
                    elif block.items:
                        preview_parts.append("• " + "; ".join(item[:80] for item in block.items[:3]))
                    elif block.table and block.table.columns:
                        preview_parts.append(f"[表格] 列: {', '.join(block.table.columns[:5])}")
                preview = " | ".join(preview_parts[:3])
                if len(preview) > 300:
                    preview = preview[:300] + "…"
                section_lines.append(f"  [{i}] {sec.heading}")
                if preview:
                    section_lines.append(f"      {preview}")

            # ── Generate follow-up questions based on report context ──
            follow_ups: list[str] = [
                "📊 想深入了解某个章节的详细数据或进行下钻分析？",
            ]
            if result.insight_count > 0:
                follow_ups.append("🔍 需要对某个分析洞察做进一步的归因或对比？")
            if result.evidence_count > 0:
                follow_ups.append("📈 想从其他维度（时间、地域、品类等）查看数据？")
            follow_ups.append("📥 需要下载其他格式（如 HTML）的报告？")

            # ── Assemble final_summary ────────────────────────────────
            # Format file size
            if file_size < 1024:
                size_str = f"{file_size}B"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.0f}KB"
            else:
                size_str = f"{file_size / 1024 / 1024:.1f}MB"

            sec_heading_list = "\n".join(
                f"  - {s.heading}" for s in report_spec.sections
            )
            result.final_summary = (
                f"✅ 报告已完整生成，以下是完整内容摘要，请直接呈现给用户：\n\n"
                f"## 报告概览\n"
                f"  - **标题**: {result.title}\n"
                f"  - **章节**: {result.section_count} 个章节\n"
                f"  - **数据依据**: {result.evidence_count} 项证据\n"
                f"  - **分析洞察**: {result.insight_count} 项洞察\n"
                f"  - **生成耗时**: {_fmt_duration(total_time)}\n\n"
                f"## 章节详情\n"
                f"{chr(10).join(section_lines)}\n\n"
                f"## 报告文件\n"
                f"  - 报告 ID: `{artifact_id}`\n"
                f"  - 文件路径: {file_path}\n"
                f"  - 文件大小: {size_str}\n\n"
                f"## 接下来您可以\n"
                + "\n".join(f"  - {q}" for q in follow_ups) +
                "\n\n"
                "⚠️ **重要：报告已完整生成，请将以上信息直接呈现给用户。**\n"
                "禁止再调用任何工具（generate_report、check_report_status、bash、parse_pdf 等），"
                "禁止读取或操作报告文件。报告内容摘要已在上面完整给出。"
            )

            logger.info("=" * 70)
            logger.info("[Pipeline] ╔══ 报告生成完成 ══╗")
            logger.info("[Pipeline]   Total time: %s", _fmt_duration(total_time))
            logger.info("[Pipeline]   Layers: 7/7 completed successfully")
            logger.info("[Pipeline]   Summary: %d sections, %d evidence, %d insights",
                        result.section_count, result.evidence_count, result.insight_count)
            logger.info("[Pipeline]   Artifact: %s", artifact_id)
            logger.info("[Pipeline]   Download: %s", download_url)
            logger.info("[Pipeline]   File: %s", file_path)
            logger.info("=" * 70)
            self._log_layer_result(7, f"artifact={artifact_id}, size={file_size} bytes")

            return result

        except Exception as e:
            total_time = time.time() - self._start_time
            logger.exception("[Pipeline] ❌ 管道执行失败 [%s] — %s", _fmt_duration(total_time), e)
            return PipelineResult(
                success=False,
                error=str(e),
                title=title,
            )

    async def _execute_plan(
        self,
        business_dag: BusinessDAG,
        datasource_metadata: dict[str, Any],
        document_path: str = "",
    ) -> list[Any]:
        """Execute a Business DAG through the Execution Layer.

        Uses ExecutionPlanner to convert Business DAG → Execution DAG,
        then ExecutionRuntime to run it with registered Workers.
        """
        from app.gateway.planning.capability_registry import get_capability_registry
        from app.gateway.workers.doc_worker import DocxWorker, PdfMetadataWorker, PdfWorker
        from app.gateway.workers.sql_worker import SQLWorker

        registry = get_capability_registry()
        logger.info("[Pipeline]   Registry: %s", registry.summary())

        # ── Register all available workers ────────────────────────────
        # Always register SQL worker
        if not registry.get_worker("sql"):
            registry.register_worker(SQLWorker())
            logger.info("[Pipeline]   Registered SQLWorker")

        # Register document workers (will be used below only if document_path is set)
        doc_workers = [PdfWorker(), DocxWorker(), PdfMetadataWorker()]
        for w in doc_workers:
            if not registry.get_worker(w.name):
                registry.register_worker(w)
                logger.info("[Pipeline]   Registered %s (capability=%s)", w.name, w.capability)

        # Build worker_map for ExecutionRuntime
        worker_map: dict[str, Any] = {}
        for cap in registry.list_capabilities():
            workers = registry.get_workers(cap)
            for w in workers:
                worker_map[w.name] = w
                logger.info("[Pipeline]   Worker available: %s (capability=%s)", w.name, cap)

        if not worker_map:
            logger.warning("[Pipeline]   No workers registered, returning empty evidence")
            return []

        # Resolve document_path from sandbox virtual path → host path
        resolved_doc_path = ""
        if document_path:
            try:
                import os

                # Walk all user threads to find the file
                base = get_paths().base_dir
                users_dir = base / "users"
                if users_dir.exists():
                    for user_dir in users_dir.iterdir():
                        threads_dir = user_dir / "threads"
                        if not threads_dir.exists():
                            continue
                        for thread_dir in threads_dir.iterdir():
                            candidate = thread_dir / "user-data" / "uploads" / os.path.basename(document_path)
                            if candidate.exists():
                                resolved_doc_path = str(candidate)
                                logger.info("[Pipeline]   Resolved document_path → %s", resolved_doc_path)
                                break
                        if resolved_doc_path:
                            break
                if not resolved_doc_path:
                    logger.warning("[Pipeline]   Could not resolve document_path on host: %s", document_path)
            except Exception as e:
                logger.warning("[Pipeline]   Error resolving document_path: %s", e)

        # Plan: Business DAG → Execution DAG
        planner = ExecutionPlanner(registry)

        # ── Build datasource_info ─────────────────────────────────────
        # Always include sql capability
        datasource_info = [{
            "datasource_id": "main",
            "datasource_type": "mysql",
            "capabilities": ["sql"],
        }]
        # When a document is uploaded, also inject document_parse capability
        if resolved_doc_path:
            datasource_info.append({
                "datasource_id": "doc_upload",
                "datasource_type": "file",
                "capabilities": ["document_parse", "file", "pdf"],
            })
        logger.info("[Pipeline]   Business tasks to plan: %s", list(business_dag.tasks.keys()))
        exec_dag = planner.plan(business_dag, datasource_info)

        if not exec_dag.tasks:
            logger.warning("[Pipeline]   Execution DAG is empty — no workers matched business tasks")
            logger.info("[Pipeline]   Business tasks: %s", list(business_dag.tasks.keys()))
            return []

        # Log execution plan
        for task in exec_dag.tasks.values():
            logger.info(
                "[Pipeline]   Task: %s → worker=%s, deps=%s",
                task.task_id, task.capability,
                task.dependencies or "none",
            )

        # Execute
        runtime = ExecutionRuntime(worker_map, max_concurrency=4)
        context: dict[str, Any] = {"datasource_metadata": datasource_metadata}
        # Pass resolved document path so workers can find files on host
        if resolved_doc_path:
            context["resolved_doc_path"] = resolved_doc_path
        logger.info("[Pipeline]   Starting ExecutionRuntime with %d tasks, concurrency=%d",
                    len(exec_dag.tasks), 4)
        t0 = time.time()
        report = await runtime.execute(exec_dag, context)
        dt = time.time() - t0

        # Log execution report
        logger.info("[Pipeline]   ExecutionRuntime report:")
        logger.info("[Pipeline]     Duration: %s", _fmt_duration(dt))
        logger.info("[Pipeline]     Tasks: %d total, %d ok, %d failed, %d skipped",
                    report.total_tasks, report.succeeded, report.failed, report.skipped)
        for task_id, tr in report.task_results.items():
            if not tr.success:
                logger.warning("[Pipeline]     ❌ Task %s failed: %s", task_id, tr.error)
            elif tr.evidence:
                logger.info("[Pipeline]     ✔ Task %s → %d evidence in %s",
                            task_id, len(tr.evidence), _fmt_duration(tr.duration_ms / 1000))

        return report.all_evidence

    async def _render_and_store(
        self,
        report_spec: ReportSpec,
        title: str,
        user_id: str,
        conversation_id: str,
        file_format: str,
    ) -> tuple[str, str, str]:
        """Render ReportSpec to file and register as artifact."""
        if file_format == "docx":
            from app.gateway.services_v1.renderer_docx import DocxRenderer
            renderer = DocxRenderer()
            logger.info("[Pipeline]   Using DocxRenderer")
        else:
            from app.gateway.services_v1.renderer_html import HtmlRenderer
            renderer = HtmlRenderer()
            logger.info("[Pipeline]   Using HtmlRenderer")

        t0 = time.time()
        file_content = renderer.render(report_spec)
        dt = time.time() - t0
        ext = renderer.file_extension
        logger.info("[Pipeline]   Render took %s, size=%d bytes", _fmt_duration(dt), len(file_content))

        from app.gateway.services_v1.db_utils import slugify
        slug = slugify(title)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        filename = f"{slug}_{ts}.{ext}"

        base = get_paths().base_dir
        output_dir = base / "users" / user_id / "threads" / conversation_id / "outputs" / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / filename
        file_path.write_bytes(file_content)

        download_url = f"/api/v1/artifacts/{artifact_id}"
        logger.info("[Pipeline]   Saved to: %s", file_path)

        # Register in DB + memory
        from app.gateway.routers.v1.artifacts import register_artifact
        from app.gateway.services_v1.artifact_service import artifact_service

        register_artifact(artifact_id, str(file_path))

        try:
            await artifact_service.create_artifact(
                conversation_id=conversation_id,
                name=title,
                artifact_type="report",
                artifact_id=artifact_id,
                meta_json={"title": title, "format": file_format},
            )
            await artifact_service.add_artifact_file(
                artifact_id=artifact_id,
                file_format=file_format,
                filename=filename,
                file_path=str(file_path),
                download_url=download_url,
                file_size=len(file_content),
                file_id=artifact_id,
            )
            logger.info("[Pipeline]   Artifact registered in DB: %s", artifact_id)
        except Exception as e:
            logger.warning("[Pipeline]   Failed to persist artifact to DB: %s — in-memory only", e)

        return artifact_id, download_url, str(file_path)
