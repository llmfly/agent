"""Planning data models: Business DAG, Report Outline, Section definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BusinessTask:
    """A business-level task in the Business DAG.

    Planner outputs these. They describe *what* to do, not *how*.
    """

    id: str = ""
    name: str = ""
    description: str = ""
    input: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)


@dataclass
class BusinessDAG:
    """The complete business plan — a DAG of BusinessTasks."""

    title: str = ""
    tasks: dict[str, BusinessTask] = field(default_factory=dict)

    def add(self, task: BusinessTask) -> None:
        self.tasks[task.id] = task

    def get_roots(self) -> list[BusinessTask]:
        return [t for t in self.tasks.values() if not t.dependencies]


@dataclass
class SectionDef:
    """A single section in the report outline."""

    section_id: str = ""
    heading: str = ""
    required_insights: list[str] = field(default_factory=list)


@dataclass
class ReportOutline:
    """Report chapter structure — decided by Planner, consumed by Composer."""

    sections: list[SectionDef] = field(default_factory=list)

    def add(self, section: SectionDef) -> None:
        self.sections.append(section)

    def get_required_insight_types(self) -> set[str]:
        types: set[str] = set()
        for s in self.sections:
            types.update(s.required_insights)
        return types
