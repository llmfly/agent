"""Planner Plugins — convert schema + user query into executable task plans."""

from __future__ import annotations

import logging
from typing import Any

from app.gateway.workflow.plugins import PlannerPlugin

logger = logging.getLogger(__name__)


class DAGSQLPlanner(PlannerPlugin):
    """Default planner: uses LLM to generate a DAG of SQL query tasks.

    Delegates to the existing _step_report_planner logic in report_workflow.
    """

    def __init__(self, llm: Any | None = None) -> None:
        self._llm = llm

    async def plan(
        self,
        user_query: str,
        schema_text: str,
        user_tables: list[str] | None = None,
    ) -> list[dict]:
        from app.gateway.services_v1.report_workflow import _step_report_planner, WorkflowContext

        # Build a minimal WorkflowContext for the planner step
        ctx = WorkflowContext(
            user_query=user_query,
            schema_text=schema_text,
            relevant_tables=user_tables or [],
        )
        if self._llm:
            ctx._llm = self._llm

        # The planner populates ctx.plan_json and ctx.tasks
        await _step_report_planner(ctx)

        return [
            {
                "task_id": t.task_id,
                "purpose": t.purpose,
                "table": t.table,
                "sql": t.sql,
                "dependencies": t.dependencies,
                "dimensions": t.dimensions,
                "metrics": t.metrics,
                "filters": t.filters,
            }
            for t in ctx.tasks
        ]


class NarrativePlanner(PlannerPlugin):
    """Simple planner for narrative/text reports without SQL queries."""

    async def plan(
        self,
        user_query: str,
        schema_text: str,
        user_tables: list[str] | None = None,
    ) -> list[dict]:
        # No SQL tasks — just markdown narrative
        return [
            {
                "task_id": "narrative_main",
                "purpose": user_query,
                "table": "",
                "sql": None,
                "dependencies": [],
            }
        ]
