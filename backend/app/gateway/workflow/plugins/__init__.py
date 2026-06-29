"""Plugin interfaces for the Universal Workflow Engine."""

from __future__ import annotations

from app.gateway.workflow.plugins.data_source_plugin import (
    DataSourcePlugin,
    FileDataSourcePlugin,
    MySQLDataSourcePlugin,
)
from app.gateway.workflow.plugins.planner_plugin import (
    DAGSQLPlanner,
    NarrativePlanner,
    PlannerPlugin,
)
from app.gateway.workflow.plugins.renderer_plugin import (
    DocxRendererPlugin,
    HtmlRendererPlugin,
    RendererPlugin,
    ScriptRendererPlugin,
)

__all__ = [
    # Base interfaces
    "DataSourcePlugin",
    "PlannerPlugin",
    "RendererPlugin",
    # DataSource implementations
    "MySQLDataSourcePlugin",
    "FileDataSourcePlugin",
    # Planner implementations
    "DAGSQLPlanner",
    "NarrativePlanner",
    # Renderer implementations
    "DocxRendererPlugin",
    "HtmlRendererPlugin",
    "ScriptRendererPlugin",
]
