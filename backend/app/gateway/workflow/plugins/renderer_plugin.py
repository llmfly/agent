"""Renderer Plugins — convert insights + data into file bytes."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Any

from app.gateway.services_v1.renderer_docx import DocxRenderer
from app.gateway.services_v1.renderer_html import HtmlRenderer
from app.gateway.workflow.plugins import RendererPlugin

logger = logging.getLogger(__name__)


class DocxRendererPlugin(RendererPlugin):
    """Render report as DOCX using the existing DocxRenderer."""

    def __init__(self) -> None:
        self._renderer = DocxRenderer()

    @property
    def file_extension(self) -> str:
        return "docx"

    async def render(self, insights: str, task_results: list[dict], title: str) -> bytes:
        # Build a ReportSpec from insights + task results
        from app.gateway.schemas.v1.reports import (
            ContentBlock,
            ReportSection,
            ReportSpec,
            TableContent,
        )

        sections = [
            ReportSection(
                heading="执行摘要",
                blocks=[ContentBlock(type="text", content=insights)],
            )
        ]
        for tr in task_results:
            rows = tr.get("rows", [])
            cols = tr.get("columns", [])
            blocks: list[ContentBlock] = []
            if tr.get("insight_text"):
                blocks.append(ContentBlock(type="text", content=tr["insight_text"]))
            if rows and cols:
                blocks.append(
                    ContentBlock(
                        type="table",
                        content=TableContent(columns=cols, rows=rows[:50]),
                    )
                )
            sections.append(
                ReportSection(
                    heading=tr.get("purpose", "数据明细"),
                    blocks=blocks,
                )
            )

        spec = ReportSpec(title=title, sections=sections)
        return self._renderer.render(spec)


class HtmlRendererPlugin(RendererPlugin):
    """Render report as HTML using the existing HtmlRenderer."""

    def __init__(self) -> None:
        self._renderer = HtmlRenderer()

    @property
    def file_extension(self) -> str:
        return "html"

    async def render(self, insights: str, task_results: list[dict], title: str) -> bytes:
        from app.gateway.schemas.v1.reports import (
            ContentBlock,
            ReportSection,
            ReportSpec,
            TableContent,
        )

        sections = [
            ReportSection(
                heading="执行摘要",
                blocks=[ContentBlock(type="text", content=insights)],
            )
        ]
        for tr in task_results:
            rows = tr.get("rows", [])
            cols = tr.get("columns", [])
            blocks: list[ContentBlock] = []
            if tr.get("insight_text"):
                blocks.append(ContentBlock(type="text", content=tr["insight_text"]))
            if rows and cols:
                blocks.append(
                    ContentBlock(
                        type="table",
                        content=TableContent(columns=cols, rows=rows[:50]),
                    )
                )
            sections.append(
                ReportSection(
                    heading=tr.get("purpose", "数据明细"),
                    blocks=blocks,
                )
            )

        spec = ReportSpec(title=title, sections=sections)
        return self._renderer.render(spec)


class ScriptRendererPlugin(RendererPlugin):
    """Render report by calling an external Python script (used by skills).

    The script receives metrics JSON + analysis markdown and produces a .docx.
    """

    def __init__(self, script_path: str, file_ext: str = "docx") -> None:
        self._script_path = Path(script_path)
        self._file_ext = file_ext

    @property
    def file_extension(self) -> str:
        return self._file_ext

    async def render(self, insights: str, task_results: list[dict], title: str) -> bytes:
        import tempfile
        import uuid

        output_dir = Path(tempfile.mkdtemp())
        output_name = f"report_{uuid.uuid4().hex[:8]}"
        output_path = output_dir / f"{output_name}.{self._file_ext}"

        cmd = [
            "python", str(self._script_path),
            "--metrics-json", "-",
            "--analysis-md", "-",
            "--output-dir", str(output_dir),
            "--output-name", output_name,
            "--no-timestamp",
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        import json
        stdin_data = json.dumps({"insights": insights, "tasks": task_results}, ensure_ascii=False).encode("utf-8")
        stdout, stderr = await proc.communicate(input=stdin_data)

        if proc.returncode != 0:
            logger.error("Script renderer failed (exit=%d): %s", proc.returncode, stderr.decode())
            raise RuntimeError(f"Script renderer exited with code {proc.returncode}: {stderr.decode()}")

        if not output_path.exists():
            raise FileNotFoundError(f"Script renderer did not produce output: {output_path}")

        content = output_path.read_bytes()
        # Cleanup
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)
        return content
