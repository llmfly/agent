"""Report generation service.

Orchestrates the end-to-end report generation pipeline:

1. Collect data sources and conversation context
2. Invoke the agent (via existing runtime) with a structured prompt
3. Parse the agent response into ReportSpec
4. Render ReportSpec into DOCX / HTML / PDF
5. Save artifacts to the conversation's output directory
6. Track report job status
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from app.gateway.schemas.v1.data_sources import DataSourceResponse
from app.gateway.schemas.v1.reports import (
    Citation,
    ContentBlock,
    ReportArtifact,
    ReportCreateRequest,
    ReportSection,
    ReportSpec,
    ReportStatusResponse,
    TableContent,
)
from app.gateway.services_v1.data_source_service import DataSourceService
from app.gateway.services_v1.renderer_base import BaseRenderer
from app.gateway.services_v1.renderer_docx import DocxRenderer
from app.gateway.services_v1.renderer_html import HtmlRenderer
from app.gateway.routers.v1.artifacts import register_artifact

logger = logging.getLogger(__name__)

# Module-level reference to the FastAPI app, set during gateway lifespan.
# Needed by background report-generation tasks to access app.state.run_event_store
# (messages) without a request context.
_report_app: FastAPI | None = None


def set_report_app(app: FastAPI) -> None:
    """Store the FastAPI app reference for background report tasks."""
    global _report_app
    _report_app = app


# ---------------------------------------------------------------------------
# Slugify helper
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Convert text to a safe filename slug."""
    import re
    # Replace non-alphanumeric chars (except Chinese, hyphens, underscores) with hyphens
    text = re.sub(r"[^\w\s\u4e00-\u9fff-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text[:100] or "report"


def _extract_text_content(raw: Any) -> str:
    """Extract plain text from event-store message content.

    Handles both plain strings and OpenAI-style content block lists.
    """
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        inner = raw.get("content", "")
        if isinstance(inner, str):
            return inner
        if isinstance(inner, list):
            texts = [part.get("text", "") for part in inner if isinstance(part, dict) and part.get("type") == "text"]
            return " ".join(texts)
        return str(inner)
    if isinstance(raw, list):
        texts = [part.get("text", "") for part in raw if isinstance(part, dict) and part.get("type") == "text"]
        return " ".join(texts)
    return str(raw)


# ---------------------------------------------------------------------------
# In-memory report job store
# ---------------------------------------------------------------------------

REPORT_TYPES_SECTIONS: dict[str, list[str]] = {
    "analysis": [
        "执行摘要",
        "背景与数据来源",
        "核心问题分析",
        "关键发现",
        "问答洞察总结",
        "风险与建议",
        "下一步行动",
        "附录",
    ],
    "summary": [
        "概览",
        "主要问题与回答",
        "关键结论",
        "待办事项",
    ],
    "research": [
        "研究背景",
        "方法论",
        "核心发现",
        "数据分析",
        "讨论",
        "结论与建议",
        "参考资料",
    ],
    "meeting_notes": [
        "会议基本信息",
        "参会人员",
        "讨论内容",
        "关键决策",
        "行动项",
    ],
    "decision_memo": [
        "背景",
        "问题陈述",
        "选项分析",
        "推荐方案",
        "风险与缓解措施",
        "执行计划",
    ],
}


class ReportJobRecord:
    """Internal report job record tracking generation status."""

    def __init__(
        self,
        report_id: str,
        conversation_id: str,
        title: str,
        status: str = "queued",
        summary: str = "",
        artifacts: list[ReportArtifact] | None = None,
        error: str | None = None,
    ) -> None:
        self.report_id = report_id
        self.conversation_id = conversation_id
        self.title = title
        self.status = status
        self.summary = summary
        self.artifacts = artifacts or []
        self.error = error
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at
        self.usage: dict[str, int] | None = None
        self.datasource_ids: list[str] = []
        self.format: list[str] = []
        self.sections: list[str] | None = None
        self.user_query: str | None = None

    def to_response(self) -> ReportStatusResponse:
        """Convert to response DTO."""
        return ReportStatusResponse(
            report_id=self.report_id,
            conversation_id=self.conversation_id,
            status=self.status,
            title=self.title,
            summary=self.summary,
            artifacts=self.artifacts,
            error=self.error,
            created_at=self.created_at,
            updated_at=self.updated_at,
            usage=self.usage,
        )


# In-memory report job store
_report_jobs: dict[str, ReportJobRecord] = {}

# Renderer registry
_renderers: dict[str, BaseRenderer] = {}


def _get_renderer(fmt: str) -> BaseRenderer | None:
    """Get a renderer by format name."""
    if fmt not in _renderers:
        try:
            if fmt == "docx":
                _renderers[fmt] = DocxRenderer()
            elif fmt == "html":
                _renderers[fmt] = HtmlRenderer()
        except ImportError as e:
            logger.warning("Renderer for %s not available: %s", fmt, e)
            return None
    return _renderers.get(fmt)


# ---------------------------------------------------------------------------
# Report generation prompt template
# ---------------------------------------------------------------------------

REPORT_GENERATION_PROMPT = """你是一个专业的报告生成助手。请根据用户提供的资料和对话内容，生成一份结构化的报告。

## 报告要求
- 报告标题: {title}
- 报告类型: {report_type}
- 语言: {language}
- 风格: {style}

## 数据源资料
{datasource_content}

## 对话问答内容
{conversation_content}

## 报告章节要求
以下章节结构请严格遵循（如有自定义章节请使用自定义）：
{sections}

## 输出格式要求
请严格按照以下 JSON 格式输出报告内容，不要包含其他文字：

```json
{{
  "title": "报告标题",
  "subtitle": "报告副标题（可选）",
  "sections": [
    {{
      "heading": "章节标题",
      "content": [
        {{"type": "paragraph", "text": "段落文本"}},
        {{"type": "bullets", "items": ["要点1", "要点2"]}},
        {{"type": "numbered_list", "items": ["条目1", "条目2"]}},
        {{"type": "table", "table": {{"columns": ["列1", "列2"], "rows": [["值1", "值2"]]}}}},
        {{"type": "code", "code": "代码内容", "language": "python"}},
        {{"type": "quote", "text": "引用文本"}}
      ]
    }}
  ],
  "citations": [
    {{"id": "src_001", "label": "来源描述", "source_type": "datasource", "locator": "位置说明"}}
  ]
}}
```

注意事项：
1. 报告内容必须基于数据源和对话内容，不得编造信息
2. 每个引用来源必须在 citations 中标注
3. 内容要详尽、专业、有深度
4. 使用 Markdown 风格的段落，包含标题、列表、表格等形式
5. 输出必须是合法的 JSON 格式
"""


class ReportService:
    """Service for end-to-end report generation."""

    def __init__(self, data_source_service: DataSourceService) -> None:
        self._data_source_service = data_source_service

    async def create_report(
        self,
        conversation_id: str,
        request: ReportCreateRequest,
        user_id: str = "anonymous",
        run_id: str | None = None,
    ) -> ReportStatusResponse:
        """Create and trigger a report generation job (async)."""
        report_id = f"rep_{uuid.uuid4().hex[:12]}"

        # Option B: Create persistent DB artifact record (report_id matches artifact_id)
        try:
            from app.gateway.services_v1.artifact_service import artifact_service
            await artifact_service.create_artifact(
                conversation_id=conversation_id,
                name=request.title,
                artifact_type="report",
                run_id=run_id,
                meta_json={
                    "report_type": request.report_type,
                    "datasource_ids": request.datasource_ids,
                    "user_query": request.user_query,
                    "format": request.format,
                },
                artifact_id=report_id,
            )
        except Exception as e:
            logger.error("Failed to create report artifact in database: %s", e)

        record = ReportJobRecord(
            report_id=report_id,
            conversation_id=conversation_id,
            title=request.title,
            status="processing",
        )
        record.datasource_ids = request.datasource_ids
        record.format = request.format
        record.sections = request.sections
        record.user_query = request.user_query

        _report_jobs[report_id] = record

        # Trigger background generation
        import asyncio

        asyncio.ensure_future(
            self._generate_report(report_id, conversation_id, request, user_id)
        )

        return record.to_response()

    async def get_report(self, report_id: str) -> ReportStatusResponse | None:
        """Get report status by ID."""
        # 1. Try DB first
        try:
            from app.gateway.services_v1.artifact_service import artifact_service
            art = await artifact_service.get_artifact(report_id)
            if art is not None:
                artifacts_list = [
                    ReportArtifact(
                        artifact_id=f.file_id,
                        format=f.file_format,
                        filename=f.filename,
                        url=f.download_url,
                    )
                    for f in art.files
                ]
                return ReportStatusResponse(
                    report_id=art.artifact_id,
                    conversation_id=art.conversation_id,
                    status=art.status,
                    title=art.name,
                    summary=art.meta_json.get("summary", f"基于 {len(art.meta_json.get('datasource_ids', []))} 个数据源生成。"),
                    artifacts=artifacts_list,
                    error=art.error_message,
                    created_at=art.created_at.isoformat(),
                    updated_at=art.updated_at.isoformat(),
                    usage=art.meta_json.get("usage"),
                )
        except Exception as e:
            logger.error("Failed to query report from DB: %s", e)

        # 2. Fallback to in-memory store
        record = _report_jobs.get(report_id)
        if record is None:
            return None
        return record.to_response()

    async def _generate_report(
        self,
        report_id: str,
        conversation_id: str,
        request: ReportCreateRequest,
        user_id: str = "anonymous",
    ) -> None:
        """Background task: generate the report.

        1. Collect data sources content
        2. Collect conversation messages
        3. Build prompt and invoke agent
        4. Parse agent response into ReportSpec
        5. Render to requested formats
        6. Save artifacts
        """
        record = _report_jobs.get(report_id)
        if record is None:
            logger.error("Report job %s not found for background generation", report_id)
            return

        try:
            # Step 1: Get data source content
            datasource_content = await self._data_source_service.get_all_content(
                conversation_id, request.datasource_ids or None,
                user_query=request.user_query,
            )

            # Step 2: Get conversation messages (simplified for now)
            conversation_content = await self._get_conversation_content(conversation_id)

            # Step 3: Build prompt and invoke agent
            sections_str = "\n".join(
                f"- {s}" for s in (request.sections or REPORT_TYPES_SECTIONS.get(request.report_type, []))
            )

            prompt = REPORT_GENERATION_PROMPT.format(
                title=request.title,
                report_type=request.report_type,
                language=request.language,
                style=request.style,
                datasource_content=datasource_content or "（无数据源资料）",
                conversation_content=conversation_content or "（无对话内容）",
                sections=sections_str,
            )

            # Step 4: Parse ReportSpec from agent output
            spec = await self._invoke_report_agent(prompt, report_id)

            if spec is None:
                raise ValueError("Report agent returned no valid ReportSpec")

            # Step 5: Render to requested formats
            artifacts: list[ReportArtifact] = []
            for fmt in request.format:
                try:
                    artifact = await self._render_and_save(
                        spec=spec,
                        fmt=fmt,
                        conversation_id=conversation_id,
                        report_id=report_id,
                        user_id=user_id,
                    )
                    if artifact:
                        artifacts.append(artifact)
                except Exception as e:
                    logger.error("Failed to render format %s for report %s: %s", fmt, report_id, e)

            # Step 6: Update record
            record.status = "success"
            record.artifacts = artifacts
            record.summary = f"报告已基于 {len(request.datasource_ids)} 个数据源生成。"
            record.updated_at = datetime.now(timezone.utc).isoformat()

            # DB update
            try:
                from app.gateway.services_v1.artifact_service import artifact_service
                await artifact_service.update_artifact_status(
                    artifact_id=report_id,
                    status="success",
                    meta_json={
                        "summary": record.summary,
                    }
                )
            except Exception as dbe:
                logger.error("Failed to update report status to success in DB: %s", dbe)

            logger.info(
                "Report %s generated successfully: %d artifacts",
                report_id,
                len(artifacts),
            )

        except Exception as e:
            logger.exception("Report generation failed for %s", report_id)
            record.status = "failed"
            record.error = str(e)
            record.updated_at = datetime.now(timezone.utc).isoformat()

            # DB update
            try:
                from app.gateway.services_v1.artifact_service import artifact_service
                await artifact_service.update_artifact_status(
                    artifact_id=report_id,
                    status="failed",
                    error_message=str(e),
                )
            except Exception as dbe:
                logger.error("Failed to update report status to failed in DB: %s", dbe)

    async def _get_conversation_content(self, conversation_id: str) -> str:
        """Get conversation (thread) message content for report context.

        Fetches all displayable messages from the run event store.
        """
        global _report_app
        if _report_app is None:
            logger.warning("Report app not initialized — cannot fetch conversation content")
            return ""
        event_store = getattr(_report_app.state, "run_event_store", None)
        if event_store is None:
            logger.warning("run_event_store not available on app.state")
            return ""
        try:
            messages = await event_store.list_messages(conversation_id, limit=100)
            return self._format_messages(messages)
        except Exception as e:
            logger.warning("Failed to get conversation content: %s", e)
            return ""

    @staticmethod
    def _format_messages(messages: list[dict]) -> str:
        """Format event-store messages into readable text for the report prompt."""
        parts = []
        for msg in messages:
            event_type = msg.get("event_type", "")
            if event_type == "human_message":
                role = "用户"
            elif event_type == "ai_message":
                role = "AI"
            else:
                continue  # skip tool_call / trace / lifecycle events

            raw = msg.get("content", "")
            text = _extract_text_content(raw)
            if text:
                parts.append(f"[{role}]: {text}")
        return "\n\n".join(parts)

    async def _invoke_report_agent(self, prompt: str, report_id: str) -> ReportSpec | None:
        """Invoke the LLM to generate a ReportSpec from the prompt.

        Uses the configured model directly (bypasses the full agent
        runtime for reliability). In production, this should be wired
        through the existing model factory.
        """
        try:
            from deerflow.models.factory import create_chat_model
            from deerflow.config.app_config import get_app_config
            from langchain_core.messages import HumanMessage, SystemMessage

            app_config = get_app_config()
            # Use the first available model
            model_configs = app_config.models
            if not model_configs:
                logger.error("No models configured for report generation")
                return self._generate_report_fallback(prompt)

            # Use the first configured model
            model_name = model_configs[0].name
            model = create_chat_model(model_name, app_config=app_config)

            system_msg = SystemMessage(
                content="你是一个专业的报告生成助手。严格按照用户要求的 JSON 格式输出报告内容，不要包含 Markdown 代码块包裹，直接输出纯 JSON。"
            )
            human_msg = HumanMessage(content=prompt)

            logger.info("Invoking LLM for report %s with model %s", report_id, model_name)
            response = await model.ainvoke([system_msg, human_msg])

            content = response.content if hasattr(response, 'content') else str(response)
            return self._parse_spec(content)

        except Exception as e:
            logger.warning("LLM invocation failed for report %s: %s. Using fallback.", report_id, e)
            return self._generate_report_fallback(prompt)

    def _parse_spec(self, content: str) -> ReportSpec | None:
        """Parse LLM output into a ReportSpec."""
        try:
            # Strip Markdown code block if present
            content = content.strip()
            if content.startswith("```"):
                # Find first { and last }
                start = content.find("{")
                end = content.rfind("}")
                if start >= 0 and end > start:
                    content = content[start:end + 1]

            data = json.loads(content)
            return self._dict_to_spec(data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse ReportSpec: %s", e)
            return None

    def _dict_to_spec(self, data: dict[str, Any]) -> ReportSpec:
        """Convert a parsed dict to a ReportSpec."""
        sections = []
        for s in data.get("sections", []):
            content_blocks = []
            for b in s.get("content", []):
                table_data = b.get("table")
                table_obj = None
                if table_data:
                    table_obj = TableContent(
                        columns=table_data.get("columns", []),
                        rows=table_data.get("rows", []),
                    )

                b_type = b.get("type", "paragraph")
                if b_type == "bullet":
                    b_type = "bullets"
                elif b_type == "list":
                    b_type = "bullets"
                elif b_type == "number_list":
                    b_type = "numbered_list"
                elif b_type not in ["paragraph", "bullets", "numbered_list", "table", "code", "heading", "quote", "image"]:
                    b_type = "paragraph"

                content_blocks.append(ContentBlock(
                    type=b_type,
                    text=b.get("text"),
                    items=b.get("items"),
                    table=table_obj,
                    code=b.get("code"),
                    language=b.get("language"),
                    level=b.get("level"),
                    image_url=b.get("image_url"),
                    image_alt=b.get("image_alt"),
                ))

            sections.append(ReportSection(
                heading=s.get("heading", ""),
                content=content_blocks,
            ))

        citations = []
        for c in data.get("citations", []):
            citations.append(Citation(
                id=c.get("id", f"src_{len(citations) + 1:03d}"),
                label=c.get("label", ""),
                source_type=c.get("source_type", "datasource"),
                locator=c.get("locator"),
            ))

        metadata = data.get("metadata", {})
        metadata.setdefault("author", "intelli-engine")
        metadata.setdefault("language", "zh-CN")

        return ReportSpec(
            title=data.get("title", "报告"),
            subtitle=data.get("subtitle"),
            metadata=metadata,
            sections=sections,
            citations=citations,
        )

    def _generate_report_fallback(self, prompt: str) -> ReportSpec:
        """Generate a basic ReportSpec when LLM is unavailable.

        Creates a minimal report structure so the pipeline can still
        produce output for testing/development.
        """
        from app.gateway.schemas.v1.reports import ReportSpec

        return ReportSpec(
            title="报告",
            subtitle="自动生成（LLM 暂不可用）",
            metadata={"author": "intelli-engine", "language": "zh-CN"},
            sections=[
                ReportSection(
                    heading="内容摘要",
                    content=[
                        ContentBlock(type="paragraph", text="报告正在生成中，请配置 LLM 模型后重试。"),
                    ],
                ),
            ],
        )

    async def _render_and_save(
        self,
        spec: ReportSpec,
        fmt: str,
        conversation_id: str,
        report_id: str,
        user_id: str = "anonymous",
    ) -> ReportArtifact | None:
        """Render a ReportSpec to a file format and save as artifact."""
        renderer = _get_renderer(fmt)
        if renderer is None:
            logger.warning("No renderer available for format: %s", fmt)
            return None

        try:
            content = renderer.render(spec)
            # Use slugified title for filename
            slug = _slugify(spec.title)
            filename = f"{slug}.{renderer.file_extension}"

            # Save to outputs directory
            artifact_id = f"art_{uuid.uuid4().hex[:12]}"
            output_path = self._get_artifact_path(user_id, conversation_id, report_id, filename)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(content)

            logger.info("Saved %s artifact: %s (%d bytes)", fmt, output_path, len(content))

            # Register for v1 artifact download
            register_artifact(artifact_id, str(output_path))

            # DB persistence (Option B)
            try:
                from app.gateway.services_v1.artifact_service import artifact_service
                await artifact_service.add_artifact_file(
                    artifact_id=report_id,
                    file_format=fmt,
                    filename=filename,
                    file_path=str(output_path),
                    download_url=f"/api/v1/artifacts/{artifact_id}",
                    file_size=len(content),
                    file_id=artifact_id,
                )
            except Exception as dbe:
                logger.error("Failed to save report file details to DB: %s", dbe)

            return ReportArtifact(
                artifact_id=artifact_id,
                format=fmt,
                filename=filename,
                url=f"/api/v1/artifacts/{artifact_id}",
            )
        except Exception as e:
            logger.error("Failed to render %s: %s", fmt, e)
            return None

    @staticmethod
    def _get_artifact_path(user_id: str, conversation_id: str, report_id: str, filename: str) -> Path:
        """Get the filesystem path for a report artifact.

        Path format:
          {DEER_FLOW_HOME}/users/{user_id}/threads/{conversation_id}/outputs/reports/{report_id}/{filename}
        """
        from deerflow.config.paths import get_paths
        base = get_paths().base_dir
        return base / "users" / user_id / "threads" / conversation_id / "outputs" / "reports" / report_id / filename


# Singleton
report_service = ReportService(DataSourceService())
