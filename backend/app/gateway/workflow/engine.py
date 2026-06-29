"""WorkflowEngine — orchestrates a report generation pipeline via plugins.

Usage:
    engine = WorkflowEngine()
    ctx = await engine.run(
        user_query="分析出口数据",
        metadata={...},           # datasource connection info
        data_source=MySQLDataSourcePlugin(metadata),
        planner=DAGSQLPlanner(),
        renderer=DocxRendererPlugin(),
        user_id="system",
        conversation_id="...",
    )
    # ctx.download_url → 可下载的 artifact URL
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.gateway.workflow.plugins import DataSourcePlugin, PlannerPlugin, RendererPlugin
from app.gateway.workflow.workflow_context import PluginContext

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Universal workflow engine — plugin-based report generation pipeline."""

    async def run(
        self,
        *,
        user_query: str,
        metadata: dict[str, Any],
        data_source: DataSourcePlugin,
        planner: PlannerPlugin,
        renderer: RendererPlugin,
        user_id: str = "anonymous",
        conversation_id: str = "",
        title: str = "",
        file_format: str = "docx",
    ) -> PluginContext:
        """Execute the full report generation pipeline.

        Steps:
            1. Schema Discovery (DataSourcePlugin)
            2. Planning (PlannerPlugin)
            3. Task Execution (generic runner)
            4. Rendering (RendererPlugin)
            5. Artifact Registration (finalize_report)
        """
        ctx = PluginContext(
            user_query=user_query,
            user_id=user_id,
            conversation_id=conversation_id,
            metadata=metadata,
            file_extension=file_format,
        )
        title = title or user_query

        # ── Step 1: Schema Discovery ──────────────────────────────────
        logger.info("[WorkflowEngine] Schema discovery (data_source=%s)", type(data_source).__name__)
        user_tables = metadata.get("tables")
        if user_tables and isinstance(user_tables, list):
            ctx.schema_text = await data_source.describe(user_tables)
        else:
            all_tables = await data_source.list_tables()
            ctx.schema_text = await data_source.describe(all_tables[:10])  # limit to 10

        # ── Step 2: Planning ───────────────────────────────────────────
        logger.info("[WorkflowEngine] Planning (planner=%s)", type(planner).__name__)
        tasks = await planner.plan(
            user_query=user_query,
            schema_text=ctx.schema_text,
            user_tables=user_tables if isinstance(user_tables, list) else None,
        )

        # ── Step 3: Execute Tasks ──────────────────────────────────────
        logger.info("[WorkflowEngine] Executing %d tasks", len(tasks))
        for task in tasks:
            sql = task.get("sql")
            if sql:
                try:
                    cols, rows, count = await data_source.execute(sql)
                    task["columns"] = cols
                    task["rows"] = rows
                    task["row_count"] = count
                    task["status"] = "done"
                except Exception as e:
                    task["error"] = str(e)
                    task["status"] = "failed"
                    logger.error("Task %s failed: %s", task.get("task_id"), e)
            else:
                task["status"] = "skipped"
        ctx.task_results = tasks

        # ── Step 4: Insight & Render ──────────────────────────────────
        logger.info("[WorkflowEngine] Rendering (renderer=%s)", type(renderer).__name__)
        # Build simple insights from task results
        insights_parts: list[str] = []
        for t in tasks:
            if t.get("row_count"):
                insights_parts.append(f"- {t.get('purpose', '')}: {t['row_count']} 条数据")
            if t.get("error"):
                insights_parts.append(f"- {t.get('purpose', '')}: 查询失败 - {t['error']}")
        ctx.insights = "\n".join(insights_parts) if insights_parts else "报告生成完毕。"

        ctx.file_content = await renderer.render(
            insights=ctx.insights,
            task_results=ctx.task_results,
            title=title,
        )
        ctx.file_extension = renderer.file_extension

        # ── Step 5: Finalize (persist + register artifact) ────────────
        artifact_id, download_url = await self._finalize_report(
            file_content=ctx.file_content,
            file_extension=ctx.file_extension,
            title=title,
            user_id=user_id,
            conversation_id=conversation_id,
            tasks=tasks,
            metadata=metadata,
        )
        ctx.artifact_id = artifact_id
        ctx.download_url = download_url

        logger.info("[WorkflowEngine] Done: artifact=%s url=%s", artifact_id, download_url)
        return ctx

    # ────────────────────────────────────────────────────────────────
    # Finalize: persist file + register artifact (shared by all paths)
    # ────────────────────────────────────────────────────────────────

    async def _finalize_report(
        self,
        *,
        file_content: bytes,
        file_extension: str,
        title: str,
        user_id: str,
        conversation_id: str,
        tasks: list[dict],
        metadata: dict,
    ) -> tuple[str, str]:
        """Persist the report file and register an artifact. Returns (artifact_id, download_url)."""
        from deerflow.config.paths import get_paths

        slug = _slugify(title)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        filename = f"{slug}_{ts}.{file_extension}"

        base = get_paths().base_dir
        output_dir = base / "users" / user_id / "threads" / conversation_id / "outputs" / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / filename
        file_path.write_bytes(file_content)

        # Register in DB + memory
        from app.gateway.routers.v1.artifacts import register_artifact
        from app.gateway.services_v1.artifact_service import artifact_service
        from app.gateway.services_v1.report_workflow import TaskStatus

        download_url = f"/api/v1/artifacts/{artifact_id}"
        register_artifact(artifact_id, str(file_path))

        try:
            await artifact_service.create_artifact(
                conversation_id=conversation_id,
                name=title,
                artifact_type="report",
                artifact_id=artifact_id,
                meta_json={
                    "title": title,
                    "format": file_extension,
                    "query_count": len(tasks),
                    "success_count": sum(1 for t in tasks if t.get("status") == "done"),
                    "failed_count": sum(1 for t in tasks if t.get("status") == "failed"),
                },
            )
            await artifact_service.add_artifact_file(
                artifact_id=artifact_id,
                file_format=file_extension,
                filename=filename,
                file_path=str(file_path),
                download_url=download_url,
                file_size=len(file_content),
                file_id=artifact_id,
            )
        except Exception as e:
            logger.warning("Failed to persist artifact to DB: %s", e)
            logger.warning("Artifact %s registered in memory only — will be lost on restart.", artifact_id)

        return artifact_id, download_url


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    import re
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "_", text)
    return text.strip("_")[:80]
