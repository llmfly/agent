"""WorkflowContext — shared state across all workflow plugins."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.gateway.services_v1.report_workflow import (
    WorkflowContext as _LegacyWorkflowContext,
    TaskStatus,
)


# Re-export legacy WorkflowContext for backward compatibility
# The plugin-based engine adds new fields while keeping the existing ones.
WorkflowContext = _LegacyWorkflowContext


@dataclass
class PluginContext:
    """Lightweight context passed to plugin methods during engine execution."""

    user_query: str = ""
    user_id: str = "anonymous"
    conversation_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # Outputs populated by the engine
    schema_text: str = ""
    task_results: list[dict] = field(default_factory=list)
    insights: str = ""
    report_spec: Any = None  # ReportSpec or equivalent
    file_content: bytes = field(default_factory=bytes)
    file_extension: str = "docx"
    file_name: str = ""
    artifact_id: str = ""
    download_url: str = ""
