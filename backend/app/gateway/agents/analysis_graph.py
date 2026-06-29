"""Analysis Graph — composable DAG of parallel analysis nodes.

Each analysis node produces Insights. The AnalysisGraph orchestrates
them, supporting parallel execution and inter-node dependencies.

Usage:
    graph = AnalysisGraph()
    graph.add_node(TrendAnalysis())
    graph.add_node(RiskAnalysis())
    graph.add_node(KPIAnalysis())
    graph.add_node(CompareAnalysis())
    graph.add_node(ForecastAnalysis())
    graph.add_node(SummaryAnalysis(depends_on=["trend", "risk", "kpi", "compare", "forecast"]))

    insights = await graph.run(evidence_graph, context)
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.gateway.models.evidence import EvidenceGraph
from app.gateway.models.insight import Insight, InsightMerger

logger = logging.getLogger(__name__)


class BaseAnalysisNode(ABC):
    """Base class for a single analysis node.

    Subclasses implement `analyze()` which receives the full
    EvidenceGraph and returns a list of Insights.
    """

    name: str = "base_analysis"
    insight_type: str = "summary"
    depends_on: list[str] = []

    @abstractmethod
    async def analyze(
        self,
        evidence_graph: EvidenceGraph,
        context: dict[str, Any] | None = None,
    ) -> list[Insight]:
        """Analyze evidence and produce insights.

        Args:
            evidence_graph: The aggregated evidence graph.
            context: Optional shared context (user_query, etc.).

        Returns:
            List of Insights. Never None — return empty list if no findings.
        """
        ...


@dataclass
class TrendAnalysis(BaseAnalysisNode):
    """Trend analysis — identifies patterns over time in evidence."""

    name: str = "trend_analysis"
    insight_type: str = "trend"

    async def analyze(
        self,
        evidence_graph: EvidenceGraph,
        context: dict[str, Any] | None = None,
    ) -> list[Insight]:
        """Detect trends from time-series evidence."""
        # In agent mode, this delegates to an LLM call.
        # For now, return a placeholder insight.
        return [
            Insight(
                type="trend",
                title="趋势分析",
                finding="基于数据的趋势分析",
                explanation="分析证据中的时间序列数据，识别增长、下降或周期性趋势。",
                confidence=0.7,
                evidence_refs=[e.id for e in evidence_graph.nodes.values()][:5],
            )
        ]


@dataclass
class RiskAnalysis(BaseAnalysisNode):
    """Risk analysis — identifies risks and issues from evidence."""

    name: str = "risk_analysis"
    insight_type: str = "risk"

    async def analyze(
        self,
        evidence_graph: EvidenceGraph,
        context: dict[str, Any] | None = None,
    ) -> list[Insight]:
        """Identify risks, anomalies, or negative patterns."""
        return [
            Insight(
                type="risk",
                title="风险评估",
                finding="基于数据的风险评估",
                explanation="分析数据中的异常、下降趋势、集中度风险等。",
                confidence=0.7,
                evidence_refs=[e.id for e in evidence_graph.nodes.values()][:5],
            )
        ]


@dataclass
class KPIAnalysis(BaseAnalysisNode):
    """KPI analysis — extracts key metrics and performance indicators."""

    name: str = "kpi_analysis"
    insight_type: str = "kpi"

    async def analyze(
        self,
        evidence_graph: EvidenceGraph,
        context: dict[str, Any] | None = None,
    ) -> list[Insight]:
        """Extract KPI values from evidence."""
        return [
            Insight(
                type="kpi",
                title="核心KPI",
                finding="关键指标概览",
                explanation="从数据中提取核心业务指标和性能度量。",
                confidence=0.8,
                evidence_refs=[e.id for e in evidence_graph.nodes.values()][:5],
            )
        ]


@dataclass
class CompareAnalysis(BaseAnalysisNode):
    """Compare analysis — contrasts data across dimensions."""

    name: str = "compare_analysis"
    insight_type: str = "compare"

    async def analyze(
        self,
        evidence_graph: EvidenceGraph,
        context: dict[str, Any] | None = None,
    ) -> list[Insight]:
        """Compare data across different segments, periods, or entities."""
        return [
            Insight(
                type="compare",
                title="对比分析",
                finding="多维度对比",
                explanation="对比不同维度（时间、地区、品类等）的数据差异和变化。",
                confidence=0.7,
                evidence_refs=[e.id for e in evidence_graph.nodes.values()][:5],
            )
        ]


@dataclass
class ForecastAnalysis(BaseAnalysisNode):
    """Forecast analysis — predicts future trends based on evidence."""

    name: str = "forecast_analysis"
    insight_type: str = "forecast"

    async def analyze(
        self,
        evidence_graph: EvidenceGraph,
        context: dict[str, Any] | None = None,
    ) -> list[Insight]:
        """Generate forecasts from historical data patterns."""
        return [
            Insight(
                type="forecast",
                title="趋势预测",
                finding="基于历史数据的预测",
                explanation="基于现有数据趋势，预测未来发展方向和潜在变化。",
                confidence=0.5,
                evidence_refs=[e.id for e in evidence_graph.nodes.values()][:5],
            )
        ]


@dataclass
class SummaryAnalysis(BaseAnalysisNode):
    """Summary analysis — produces an overall summary from all other insights."""

    name: str = "summary_analysis"
    insight_type: str = "summary"
    depends_on: list[str] = field(default_factory=lambda: ["trend", "risk", "kpi", "compare", "forecast"])

    async def analyze(
        self,
        evidence_graph: EvidenceGraph,
        context: dict[str, Any] | None = None,
    ) -> list[Insight]:
        """Produce an executive summary synthesizing all evidence."""
        return [
            Insight(
                type="summary",
                title="执行摘要",
                finding="综合分析总结",
                explanation="综合所有分析结果，给出整体性结论和建议。",
                confidence=0.8,
                evidence_refs=[e.id for e in evidence_graph.nodes.values()][:5],
            )
        ]


class AnalysisGraph:
    """Orchestrates multiple analysis nodes in a dependency-aware DAG.

    Supports:
    - Parallel execution of independent nodes
    - Sequential execution of dependent nodes (e.g., summary depends on all others)
    - Adding custom nodes at runtime
    """

    def __init__(self) -> None:
        self._nodes: dict[str, BaseAnalysisNode] = {}

    def add_node(self, node: BaseAnalysisNode) -> None:
        """Register an analysis node."""
        if node.insight_type in self._nodes:
            logger.warning("Overwriting existing analysis node for type %s", node.insight_type)
        self._nodes[node.insight_type] = node
        logger.info("AnalysisGraph: registered node %s (insight_type=%s)", node.name, node.insight_type)

    def remove_node(self, insight_type: str) -> None:
        """Remove a registered analysis node."""
        self._nodes.pop(insight_type, None)

    def get_node(self, insight_type: str) -> BaseAnalysisNode | None:
        """Get a registered node by insight type."""
        return self._nodes.get(insight_type)

    def list_types(self) -> list[str]:
        """List all registered insight types."""
        return list(self._nodes.keys())

    async def run(
        self,
        evidence_graph: EvidenceGraph,
        context: dict[str, Any] | None = None,
    ) -> list[Insight]:
        """Execute all analysis nodes respecting dependencies.

        Builds a dependency DAG from the nodes and executes them
        in topological order. Independent nodes run in parallel.

        Args:
            evidence_graph: Aggregated evidence from the Evidence Layer.
            context: Optional shared context.

        Returns:
            List of Insights from all nodes, merged by InsightMerger.
        """
        if not self._nodes:
            logger.warning("AnalysisGraph: no nodes registered, returning empty insights")
            return []

        # 1. Build dependency graph
        node_types = list(self._nodes.keys())
        node_set = set(node_types)
        in_degree: dict[str, int] = {}
        dependents: dict[str, list[str]] = {nt: [] for nt in node_types}

        for nt, node in self._nodes.items():
            deps = [d for d in node.depends_on if d in node_set]
            in_degree[nt] = len(deps)
            for dep in deps:
                dependents[dep].append(nt)

        # 2. Topological execution
        merger = InsightMerger()
        ready = [nt for nt, deg in in_degree.items() if deg == 0]

        while ready:
            # Execute all ready nodes in parallel
            results = await asyncio.gather(*[
                self._execute_node(nt, evidence_graph, context)
                for nt in ready
            ])

            # Collect insights and update dependency state
            for nt, insights in zip(ready, results):
                merger.add_many(insights)
                for dep in dependents[nt]:
                    in_degree[dep] -= 1

            # Next level
            ready = [nt for nt, deg in in_degree.items() if deg == 0 and nt not in ready]

        # Check for unexecuted nodes (circular dependencies)
        unexecuted = [nt for nt, deg in in_degree.items() if deg > 0]
        if unexecuted:
            logger.warning(
                "AnalysisGraph: %d nodes not executed due to circular deps: %s",
                len(unexecuted), unexecuted,
            )

        return merger.get_all()

    async def _execute_node(
        self,
        node_type: str,
        evidence_graph: EvidenceGraph,
        context: dict[str, Any] | None,
    ) -> list[Insight]:
        """Execute a single analysis node with error handling."""
        node = self._nodes.get(node_type)
        if not node:
            return []

        try:
            logger.debug("AnalysisGraph: executing node %s", node.name)
            return await node.analyze(evidence_graph, context)
        except Exception as e:
            logger.error("AnalysisGraph: node %s failed: %s", node.name, e)
            return []


# ---------------------------------------------------------------------------
# Default factory — creates a graph with all standard nodes
# ---------------------------------------------------------------------------

def create_default_analysis_graph() -> AnalysisGraph:
    """Create an AnalysisGraph pre-loaded with all standard analysis nodes."""
    graph = AnalysisGraph()
    graph.add_node(TrendAnalysis())
    graph.add_node(RiskAnalysis())
    graph.add_node(KPIAnalysis())
    graph.add_node(CompareAnalysis())
    graph.add_node(ForecastAnalysis())
    graph.add_node(SummaryAnalysis())
    return graph
