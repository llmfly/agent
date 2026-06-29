"""Insight data model — the output of the Analysis Layer consumed by the Composer.

Analysis Nodes produce Insights. The InsightMerger collects them into a list
that the Report Composer consumes, matched against Report Outline sections.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


InsightType = Literal[
    "trend",
    "risk",
    "kpi",
    "compare",
    "forecast",
    "summary",
]


@dataclass
class Citation:
    """Lightweight citation reference within an Insight."""

    evidence_id: str = ""
    label: str = ""


@dataclass
class Insight:
    """A single analytical finding — structured reasoning output.

    Analysis Nodes produce Insights. The Composer later consumes these
    and maps them to Report Outline sections.
    """

    id: str = field(default_factory=lambda: f"ins_{uuid.uuid4().hex[:12]}")
    type: InsightType = "summary"
    title: str = ""
    finding: str = ""                       # one-sentence conclusion
    explanation: str = ""                   # detailed reasoning
    confidence: float = 0.0
    evidence_refs: list[str] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "finding": self.finding,
            "explanation": self.explanation[:300],
            "confidence": self.confidence,
            "evidence_count": len(self.evidence_refs),
        }


@dataclass
class InsightMerger:
    """Collects and merges Insights from multiple Analysis Nodes."""

    insights: dict[str, Insight] = field(default_factory=dict)  # type → Insight

    def add(self, insight: Insight) -> None:
        key = insight.type
        if key in self.insights and insight.confidence > self.insights[key].confidence:
            self.insights[key] = insight
        elif key not in self.insights:
            self.insights[key] = insight

    def add_many(self, items: list[Insight]) -> None:
        for ins in items:
            self.add(ins)

    def get_by_type(self, itype: InsightType) -> list[Insight]:
        return [ins for ins in self.insights.values() if ins.type == itype]

    def get_all(self) -> list[Insight]:
        return list(self.insights.values())

    def to_prompt_context(self) -> str:
        """Serialize all insights into a concise block for the Composer."""
        lines = ["## 分析洞察摘要"]
        for ins in self.get_all():
            lines.append(f"\n### [{ins.type.upper()}] {ins.title}")
            lines.append(f"**发现**: {ins.finding}")
            if ins.explanation:
                lines.append(f"**分析**: {ins.explanation[:500]}")
            lines.append(f"**置信度**: {ins.confidence:.2f}")
            if ins.citations:
                lines.append(f"**引用**: {', '.join(c.label for c in ins.citations)}")
        return "\n".join(lines)
