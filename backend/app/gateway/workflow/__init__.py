"""Universal Workflow Engine — plugin-based report generation pipeline.

Architecture:
  Lead Agent
      │
      ▼
  WorkflowEngine.run(ctx, plugins)
      │
  ┌──────────────────────────────────────────┐
  │ DataSourcePlugin.describe() → schema     │
  │ PlannerPlugin.plan(schema) → tasks       │
  │ execute tasks (generic runner)           │
  │ RendererPlugin.render(spec) → bytes      │
  │ finalize_report(bytes) → artifact URL    │
  └──────────────────────────────────────────┘

All three report generation paths converge through the same finalize_report tool,
ensuring consistent storage and return format.
"""

from app.gateway.workflow.engine import WorkflowEngine
from app.gateway.workflow.plugins import (
    DataSourcePlugin,
    FileDataSourcePlugin,
    MySQLDataSourcePlugin,
    PlannerPlugin,
    DAGSQLPlanner,
    NarrativePlanner,
    RendererPlugin,
    DocxRendererPlugin,
    HtmlRendererPlugin,
    ScriptRendererPlugin,
)
from app.gateway.workflow.workflow_context import WorkflowContext

__all__ = [
    "WorkflowEngine",
    "WorkflowContext",
    # DataSource plugins
    "DataSourcePlugin",
    "MySQLDataSourcePlugin",
    "FileDataSourcePlugin",
    # Planner plugins
    "PlannerPlugin",
    "DAGSQLPlanner",
    "NarrativePlanner",
    # Renderer plugins
    "RendererPlugin",
    "DocxRendererPlugin",
    "HtmlRendererPlugin",
    "ScriptRendererPlugin",
]
