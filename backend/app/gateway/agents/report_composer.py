"""Report Composer Agent — writes report text from insights.

The Composer receives:
- **Report Outline** (from Planner) — defines chapter structure
- **List[Insight]** (from Analysis Layer) — distilled analytical findings

The Composer produces:
- **ReportSpec** — structured report with paragraphs, tables, lists

The Composer does NOT:
- Decide what chapters exist (Planner decides)
- Analyze raw data (Analysis Layer does)
- Render to final format (Rendering Layer does)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.gateway.models.insight import Insight
from app.gateway.planning.models import ReportOutline
from app.gateway.schemas.v1.reports import (
    Citation,
    ContentBlock,
    ReportSection,
    ReportSpec,
    TableContent,
)

logger = logging.getLogger(__name__)


REPORT_COMPOSER_SYSTEM_PROMPT = """你是一个专业的报告撰写助手。根据报告大纲和分析洞察，撰写结构化报告内容。

你的任务：
1. 将 Insight 按章节归类（根据每个章节要求的 insight 类型匹配）
2. 为每个章节撰写专业、深入的段落文字
3. 嵌入表格、数据引用等
4. 输出指定的 JSON 格式

写作要求：
- 语言专业、严谨，使用正式的报告风格
- 每个段落都要有实质性内容，不要空洞
- 数据引用必须标注来源（使用 citations）
- 内容要有逻辑结构：先概述，再展开，最后小结
- 适当使用列表、表格等形式增强可读性

请严格按照以下 JSON 格式输出：
```json
{
  "title": "报告标题",
  "subtitle": "报告副标题",
  "sections": [
    {
      "heading": "章节标题",
      "content": [
        {"type": "paragraph", "text": "段落文本..."},
        {"type": "bullets", "items": ["要点1", "要点2"]},
        {"type": "numbered_list", "items": ["条目1", "条目2"]},
        {"type": "table", "table": {"columns": ["列1", "列2"], "rows": [["值1", "值2"]]}},
        {"type": "heading", "text": "子标题", "level": 3},
        {"type": "quote", "text": "引用内容"}
      ]
    }
  ],
  "citations": [
    {"id": "src_001", "label": "来源描述", "source_type": "datasource", "locator": "具体位置"}
  ]
}
```

可用块类型: paragraph, bullets, numbered_list, table, code, heading, quote, image
"""


class ReportComposerAgent:
    """LLM-driven report composer.

    Takes a Report Outline + List[Insight] and produces a structured ReportSpec.
    """

    def __init__(self) -> None:
        self._llm = None

    async def compose(
        self,
        outline: ReportOutline,
        insights: list[Insight],
        title: str = "",
        subtitle: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ReportSpec:
        """Compose report from outline and insights.

        Args:
            outline: Report chapter structure from Planner.
            insights: Analytical insights from Analysis Layer.
            title: Report title.
            subtitle: Optional subtitle.
            context: Optional extra context.

        Returns:
            A ReportSpec ready for rendering.
        """
        # If no LLM available, use template-based composition
        if not await self._can_use_llm():
            logger.info("Composer: LLM unavailable, using template-based composition")
            return self._template_compose(outline, insights, title, subtitle)

        try:
            return await self._llm_compose(outline, insights, title, subtitle, context or {})
        except Exception as e:
            logger.warning("LLM composition failed, using template fallback: %s", e)
            return self._template_compose(outline, insights, title, subtitle)

    async def _can_use_llm(self) -> bool:
        """Check if LLM is available."""
        try:
            from deerflow.config.app_config import get_app_config
            app_config = get_app_config()
            return bool(app_config.models)
        except Exception:
            return False

    async def _llm_compose(
        self,
        outline: ReportOutline,
        insights: list[Insight],
        title: str,
        subtitle: str | None,
        context: dict[str, Any],
    ) -> ReportSpec:
        """Use LLM to compose the report."""
        if self._llm is None:
            from deerflow.config.app_config import get_app_config
            from deerflow.models.factory import create_chat_model

            app_config = get_app_config()
            self._llm = create_chat_model(app_config.models[0].name, app_config=app_config)

        # Build prompt
        outline_str = self._format_outline(outline)
        insights_str = self._format_insights(insights)

        prompt = (
            f"报告标题: {title}\n"
            f"{'副标题: ' + subtitle if subtitle else ''}\n\n"
            f"## 报告大纲\n{outline_str}\n\n"
            f"## 分析洞察\n{insights_str}\n\n"
            "请根据以上大纲和洞察，撰写报告内容并输出 JSON。"
        )

        from langchain_core.messages import HumanMessage, SystemMessage

        resp = await self._llm.ainvoke([
            SystemMessage(content=REPORT_COMPOSER_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])

        content = resp.content if hasattr(resp, "content") else str(resp)
        content = content.strip()

        if content.startswith("```"):
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                content = content[start:end + 1]

        data = json.loads(content)
        return self._dict_to_spec(data, title)

    def _template_compose(
        self,
        outline: ReportOutline,
        insights: list[Insight],
        title: str,
        subtitle: str | None,
    ) -> ReportSpec:
        """Template-based composition when LLM is unavailable.

        Maps insights to sections based on required_insight types,
        producing a structured but non-LLM-written report.
        """
        sections: list[ReportSection] = []
        citations: list[Citation] = []

        insight_by_type: dict[str, list[Insight]] = {}
        for ins in insights:
            insight_by_type.setdefault(ins.type, []).append(ins)

        for section_def in outline.sections:
            content_blocks: list[ContentBlock] = []

            for req_type in section_def.required_insights:
                matching = insight_by_type.get(req_type, [])
                for ins in matching:
                    content_blocks.append(
                        ContentBlock(type="paragraph", text=f"**{ins.title}**: {ins.finding}")
                    )
                    if ins.explanation:
                        content_blocks.append(
                            ContentBlock(type="paragraph", text=ins.explanation[:500])
                        )

                    # Add citations
                    for cit in ins.citations:
                        citations.append(Citation(
                            id=cit.evidence_id,
                            label=cit.label,
                        ))

            # If no insights matched, add a placeholder
            if not content_blocks:
                content_blocks.append(
                    ContentBlock(type="paragraph", text="（此章节内容待生成）")
                )

            sections.append(ReportSection(
                heading=section_def.heading,
                content=content_blocks,
            ))

        return ReportSpec(
            title=title,
            subtitle=subtitle,
            metadata={"author": "intelli-engine", "language": "zh-CN"},
            sections=sections,
            citations=citations,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_outline(outline: ReportOutline) -> str:
        lines = []
        for i, s in enumerate(outline.sections, 1):
            lines.append(f"  {i}. {s.heading}")
            if s.required_insights:
                lines.append(f"     需要: {', '.join(s.required_insights)}")
        return "\n".join(lines) if lines else "（无章节定义）"

    @staticmethod
    def _format_insights(insights: list[Insight]) -> str:
        lines = [f"共 {len(insights)} 个分析洞察"]
        for ins in insights:
            lines.append(f"\n  [{ins.type.upper()}] {ins.title}")
            lines.append(f"  发现: {ins.finding}")
            if ins.explanation:
                lines.append(f"  分析: {ins.explanation[:200]}")
            lines.append(f"  置信度: {ins.confidence:.2f}")
        return "\n".join(lines)

    @staticmethod
    def _dict_to_spec(data: dict[str, Any], default_title: str) -> ReportSpec:
        """Convert parsed JSON dict to ReportSpec."""
        sections = []
        for s in data.get("sections", []):
            content_blocks = []
            for b in s.get("content", []):
                b_type = b.get("type", "paragraph")

                # Normalize type names
                if b_type == "bullet":
                    b_type = "bullets"
                elif b_type == "list":
                    b_type = "bullets"
                elif b_type == "number_list":
                    b_type = "numbered_list"

                table_data = b.get("table")
                table_obj = None
                if table_data:
                    table_obj = TableContent(
                        columns=table_data.get("columns", []),
                        rows=table_data.get("rows", []),
                    )

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

        return ReportSpec(
            title=data.get("title", default_title),
            subtitle=data.get("subtitle"),
            metadata=data.get("metadata", {"author": "intelli-engine", "language": "zh-CN"}),
            sections=sections,
            citations=citations,
        )


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

async def compose_report(
    outline: ReportOutline,
    insights: list[Insight],
    title: str = "报告",
) -> ReportSpec:
    """One-shot report composition."""
    composer = ReportComposerAgent()
    return await composer.compose(outline, insights, title=title)
