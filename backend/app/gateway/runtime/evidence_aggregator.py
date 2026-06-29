"""Evidence Aggregator — standardizes, deduplicates, and graphs evidence.

Belongs to the Evidence Layer (Workflow, not Agent).
Consumes List[Evidence] from the Execution Runtime and produces
an EvidenceGraph for the Analysis Layer.
"""

from __future__ import annotations

import logging
from typing import Any

from app.gateway.models.evidence import Content, Evidence, EvidenceGraph, SourceInfo

logger = logging.getLogger(__name__)


class EvidenceAggregator:
    """Aggregates and normalizes raw evidence into an EvidenceGraph.

    Steps:
      1. Standardize field formats
      2. Deduplicate by source
      3. Sort by score
      4. Build relations → Evidence Graph
    """

    def aggregate(self, evidence_list: list[Evidence]) -> EvidenceGraph:
        """Process a flat list of Evidence into a structured EvidenceGraph."""
        graph = EvidenceGraph()

        # 1. Deduplicate by (datasource_type, datasource_id, content text preview)
        seen: set[str] = set()
        deduped: list[Evidence] = []
        for ev in evidence_list:
            key = self._dedup_key(ev)
            if key not in seen:
                seen.add(key)
                deduped.append(ev)

        # 2. Sort by score descending
        deduped.sort(key=lambda e: e.score, reverse=True)

        # 3. Add to graph
        for ev in deduped:
            graph.add(ev)

        # 4. Set roots (top-level entries with no incoming relations)
        all_related: set[str] = set()
        for ev in deduped:
            all_related.update(ev.relations)
        graph.root_ids = [ev.id for ev in deduped if ev.id not in all_related]

        logger.info(
            "EvidenceAggregator: %d raw → %d deduped → %d graph nodes",
            len(evidence_list), len(deduped), graph.total_count,
        )
        return graph

    @staticmethod
    def _dedup_key(ev: Evidence) -> str:
        """Generate a deduplication key for an Evidence item."""
        parts = [ev.source.datasource_type, ev.source.datasource_id]
        if ev.source.table:
            parts.append(ev.source.table)
        if ev.source.document_id:
            parts.append(ev.source.document_id)
        if ev.source.url:
            parts.append(ev.source.url)
        # Add content fingerprint
        if ev.content.text:
            parts.append(ev.content.text[:100])
        return "::".join(p for p in parts if p)

    @staticmethod
    def build_citation(evidence: Evidence) -> str:
        """Build a human-readable citation string from evidence."""
        s = evidence.source
        parts = []
        if s.table:
            parts.append(f"表 {s.table}")
        if s.document_id:
            parts.append(s.document_id)
        if s.url:
            parts.append(s.url)
        return " | ".join(parts) if parts else s.datasource_type
