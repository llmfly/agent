"""Report Planner Agent — produces Business DAG, Report Outline, and Analysis Requirements.

The Planner is an LLM-driven agent that understands the user's request
and produces a structured plan for report generation. It decides:

1. **Business DAG** — what data to collect and in what order
2. **Report Outline** — chapter/section structure of the final report
3. **Analysis Requirements** — what types of analysis each section needs

The Planner does NOT know about:
- Specific data sources (SQL, PDF, API, etc.)
- Worker implementations
- Execution details (those are handled by ExecutionPlanner)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.gateway.planning.models import BusinessDAG, BusinessTask, ReportOutline, SectionDef

logger = logging.getLogger(__name__)


REPORT_PLANNER_SYSTEM_PROMPT = """你是一个专业的 Report Planner。根据用户需求，制定报告生成计划。

你必须输出三样东西：
1. **Business DAG** — 业务任务依赖关系（数据收集任务）
2. **Report Outline** — 报告章节结构
3. **Analysis Requirements** — 每个章节需要哪些类型的 Insight

可用的 Insight 类型:
- trend: 趋势分析（时间序列数据变化）
- risk: 风险评估（异常、风险识别）
- kpi: 关键指标（核心业务度量）
- compare: 对比分析（多维度对比）
- forecast: 预测（未来趋势预测）
- summary: 摘要（整体性总结）

可用的 Business Task 类型:
- CollectSalesData: 收集销售/交易数据
- CollectCustomerData: 收集客户信息
- CollectMarketAnalysis: 收集市场分析资料
- CollectCompetitorInfo: 收集竞争对手信息
- CollectFinancialData: 收集财务数据
- CollectRiskData: 收集风险相关数据
- CollectTrendData: 收集趋势相关数据
- document_parse: 解析上传的文档（PDF/DOCX），提取文本内容

请严格按以下 JSON 格式输出：
```json
{
  "title": "报告标题",
  "outline": [
    {
      "section_id": "章节ID",
      "heading": "章节标题",
      "required_insights": ["insight_type1", "insight_type2"]
    }
  ],
  "business_tasks": [
    {
      "id": "bt_1",
      "name": "CollectSalesData",
      "description": "任务描述",
      "input": {"key": "value"},
      "dependencies": []
    }
  ],
  "analysis_requirements": [
    {"type": "trend", "sources": ["bt_1", "bt_2"]}
  ]
}
```
"""


@dataclass
class PlannerOutput:
    """Structured output from the Report Planner Agent.

    Contains everything needed by downstream layers:
    - ExecutionPlanner (consumes Business DAG)
    - ReportComposer (consumes Report Outline + section insight requirements)
    - AnalysisGraph (consumes Analysis Requirements)
    """

    title: str = ""
    outline: ReportOutline = field(default_factory=ReportOutline)
    business_dag: BusinessDAG = field(default_factory=BusinessDAG)
    analysis_requirements: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "outline": [
                {"section_id": s.section_id, "heading": s.heading, "required_insights": s.required_insights}
                for s in self.outline.sections
            ],
            "business_tasks": [
                {"id": t.id, "name": t.name, "description": t.description, "dependencies": t.dependencies}
                for t in self.business_dag.tasks.values()
            ],
            "analysis_requirements": self.analysis_requirements,
        }


class ReportPlannerAgent:
    """LLM-driven Report Planner.

    Produces the Business DAG, Report Outline, and Analysis Requirements
    that drive the entire report generation pipeline.

    Usage:
        planner = ReportPlannerAgent()
        output = await planner.plan(
            user_query="分析2024年欧洲市场销售数据",
            context={"region": "Europe", "period": "2024"}
        )
    """

    def __init__(self) -> None:
        self._llm = None

    async def plan(
        self,
        user_query: str,
        context: dict[str, Any] | None = None,
    ) -> PlannerOutput:
        """Plan report generation based on user query.

        Args:
            user_query: The user's natural language request.
            context: Optional context (conversation history, user preferences, etc.).

        Returns:
            A PlannerOutput with Business DAG, Report Outline, and Analysis Requirements.
        """
        try:
            result = await self._call_llm(user_query, context or {})
            return self._parse_result(result)
        except Exception as e:
            logger.warning("LLM planning failed, using fallback: %s", e)
            return self._fallback_plan(user_query)

    async def _call_llm(
        self,
        user_query: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Call LLM for report planning."""
        if self._llm is None:
            from deerflow.config.app_config import get_app_config
            from deerflow.models.factory import create_chat_model
            from langchain_core.messages import HumanMessage, SystemMessage

            app_config = get_app_config()
            if app_config.models:
                self._llm = create_chat_model(app_config.models[0].name, app_config=app_config)
            else:
                raise RuntimeError("No LLM models configured")

        context_str = json.dumps(context, ensure_ascii=False, indent=2) if context else "无"
        prompt = (
            f"用户需求: {user_query}\n\n"
            f"上下文信息:\n{context_str}\n\n"
            "请输出 JSON 格式的报告生成计划。"
        )

        resp = await self._llm.ainvoke([
            SystemMessage(content=REPORT_PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])

        content = resp.content if hasattr(resp, "content") else str(resp)
        content = content.strip()

        # Strip markdown code blocks
        if content.startswith("```"):
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                content = content[start:end + 1]

        return json.loads(content)

    def _parse_result(self, data: dict[str, Any]) -> PlannerOutput:
        """Parse LLM JSON output into PlannerOutput."""
        output = PlannerOutput(title=data.get("title", "报告"))

        # Parse outline
        for s in data.get("outline", []):
            output.outline.add(SectionDef(
                section_id=s.get("section_id", ""),
                heading=s.get("heading", ""),
                required_insights=s.get("required_insights", []),
            ))

        # Parse business tasks
        for bt in data.get("business_tasks", []):
            output.business_dag.add(BusinessTask(
                id=bt.get("id", f"bt_{len(output.business_dag.tasks) + 1}"),
                name=bt.get("name", ""),
                description=bt.get("description", ""),
                input=bt.get("input", {}),
                dependencies=bt.get("dependencies", []),
            ))

        # Parse analysis requirements
        output.analysis_requirements = data.get("analysis_requirements", [])

        logger.info(
            "Planner: title=%s, %d sections, %d tasks, %d analysis requirements",
            output.title, len(output.outline.sections),
            len(output.business_dag.tasks), len(output.analysis_requirements),
        )
        return output

    def _fallback_plan(self, user_query: str) -> PlannerOutput:
        """Generate a fallback plan when LLM is unavailable."""
        output = PlannerOutput(title=user_query[:80])

        output.outline.add(SectionDef(
            section_id="executive_summary", heading="执行摘要",
            required_insights=["summary"],
        ))
        output.outline.add(SectionDef(
            section_id="data_overview", heading="数据概览",
            required_insights=["kpi", "trend"],
        ))
        output.outline.add(SectionDef(
            section_id="analysis", heading="核心分析",
            required_insights=["trend", "compare", "risk"],
        ))
        output.outline.add(SectionDef(
            section_id="conclusion", heading="结论与建议",
            required_insights=["summary", "forecast"],
        ))

        output.business_dag.add(BusinessTask(
            id="bt_1", name="CollectSalesData",
            description="收集相关销售数据",
            input={"query": user_query},
        ))
        output.business_dag.add(BusinessTask(
            id="bt_2", name="CollectTrendData",
            description="收集趋势数据",
            dependencies=["bt_1"],
        ))

        output.analysis_requirements = [
            {"type": "trend", "sources": ["bt_1", "bt_2"]},
            {"type": "kpi", "sources": ["bt_1"]},
            {"type": "summary", "sources": ["*"]},
        ]

        return output


# ---------------------------------------------------------------------------
# Convenience function for one-shot planning
# ---------------------------------------------------------------------------

async def plan_report(
    user_query: str,
    context: dict[str, Any] | None = None,
) -> PlannerOutput:
    """One-shot report planning.

    Args:
        user_query: The user's natural language request.
        context: Optional planning context.

    Returns:
        PlannerOutput ready for downstream consumption.
    """
    agent = ReportPlannerAgent()
    return await agent.plan(user_query, context)
