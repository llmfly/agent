"""Evidence data model — the universal intermediate output format for all Workers.

All workers output List[Evidence]. Evidence Aggregator consumes these
and produces an EvidenceGraph for the Analysis Layer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


EvidenceType = Literal[
    "sql_row",
    "pdf_chunk",
    "docx_chunk",
    "search_result",
    "api_response",
    "memory_record",
    "cache_hit",
    "knowledge_chunk",
    "file_content",
    "chart_image",
    "unknown",
]


@dataclass
class SourceInfo:
    """Describes where the Evidence came from — fully traceable."""

    datasource_id: str = ""
    datasource_type: str = ""           # mysql, pdf, web, api, memory, ...
    document_id: str | None = None
    table: str | None = None
    file: str | None = None
    api: str | None = None
    url: str | None = None
    timestamp: str | None = None


@dataclass
class TableContent:
    """Tabular data within Evidence content."""

    columns: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class Content:
    """Standardized content payload — at least one field should be set."""

    text: str | None = None
    table: TableContent | None = None
    image_url: str | None = None
    structured: dict[str, Any] | None = None


@dataclass
class Citation:
    """A citation / source reference that can be rendered in reports."""

    id: str = ""
    label: str = ""
    source_type: str = "datasource"
    locator: str | None = None


@dataclass
class Evidence:
    """Universal evidence unit — output of every Worker.

    All workers must return List[Evidence]. This is the single contract
    between the Execution Layer and the Evidence Layer.
    """

    id: str = field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:12]}")
    type: EvidenceType = "unknown"
    source: SourceInfo = field(default_factory=SourceInfo)
    content: Content = field(default_factory=Content)
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    citation: Citation | None = None
    relations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for LLM prompt building."""
        return {
            "id": self.id,
            "type": self.type,
            "source": {
                "datasource_id": self.source.datasource_id,
                "datasource_type": self.source.datasource_type,
                "table": self.source.table,
                "file": self.source.file,
                "api": self.source.api,
                "url": self.source.url,
            },
            "content_preview": (
                self.content.text[:500] if self.content.text
                else f"<table {len(self.content.table.columns)} cols × {len(self.content.table.rows)} rows>"
                if self.content.table
                else "<structured>"
                if self.content.structured
                else ""
            ),
            "score": self.score,
        }


@dataclass
class EvidenceGraph:
    """Aggregated, deduplicated, sorted evidence ready for Analysis Layer."""

    nodes: dict[str, Evidence] = field(default_factory=dict)       # id → Evidence
    adjacency: dict[str, list[str]] = field(default_factory=dict)   # id → [related ids]
    root_ids: list[str] = field(default_factory=list)               # top-level entries
    total_count: int = 0
    source_types: set[str] = field(default_factory=set)

    def add(self, evidence: Evidence) -> None:
        self.nodes[evidence.id] = evidence
        self.total_count = len(self.nodes)
        self.source_types.add(evidence.type)
        if evidence.relations:
            self.adjacency[evidence.id] = evidence.relations

    def get_by_type(self, etype: EvidenceType) -> list[Evidence]:
        return [e for e in self.nodes.values() if e.type == etype]

    def get_by_source(self, datasource_id: str) -> list[Evidence]:
        return [e for e in self.nodes.values() if e.source.datasource_id == datasource_id]

    def to_prompt_context(self, max_evidences: int = 50) -> str:
        """Serialize graph to a concise text block for LLM prompt."""
        sorted_nodes = sorted(self.nodes.values(), key=lambda e: e.score, reverse=True)
        lines = [f"共 {len(sorted_nodes)} 条证据，来自 {len(self.source_types)} 种数据源"]
        for ev in sorted_nodes[:max_evidences]:
            preview = (
                ev.content.text[:200] if ev.content.text
                else f"[表格 {ev.source.table}]"
                if ev.content.table
                else "[结构化数据]"
                if ev.content.structured
                else ""
            )
            lines.append(f"  [{ev.type}] {preview} (score={ev.score:.2f})")
        return "\n".join(lines)
