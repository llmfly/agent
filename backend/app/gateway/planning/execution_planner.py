"""Execution Planner — converts Business DAG → Execution DAG.

Belongs to the Planning Layer, not the Runtime.
Queries CapabilityRegistry to resolve Business Tasks into
concrete Execution Tasks with specific Workers.
"""

from __future__ import annotations

import logging
from typing import Any

from app.gateway.planning.capability_registry import CapabilityRegistry
from app.gateway.planning.models import BusinessDAG, BusinessTask
from app.gateway.workers.base import ExecutionDAG, ExecutionTask

logger = logging.getLogger(__name__)


# Mapping from generic business task names to required capabilities.
# Execution Planner uses this to decide how to fulfill each task.
# Extend this when new business task types are added.
BUSINESS_TASK_CAPABILITIES: dict[str, list[str]] = {
    # Data collection tasks
    "CollectSalesData":           ["sql", "api", "memory"],
    "CollectCustomerData":        ["sql", "api", "memory"],
    "CollectMarketAnalysis":      ["search", "pdf", "document_parse", "knowledge", "web"],
    "CollectCompetitorInfo":      ["search", "pdf", "web"],
    "CollectFinancialData":       ["sql", "pdf", "api"],
    "CollectRiskData":            ["search", "knowledge", "api"],
    "CollectTrendData":           ["sql", "search", "api"],

    # Document parsing tasks
    "document_parse":             ["document_parse"],

    # Composite tasks (no direct worker — just DAG coordination)
    "SynthesizeAnalysis":         [],           # Analysis layer, not worker
    "WriteReport":                [],           # Composition layer, not worker

    # Generic fallback
    "default":                    ["search"],
}

# Business tasks that should be passed through to the Evidence layer
# without worker execution (they represent analysis/writing steps).
NON_EXECUTABLE_TASKS = {"SynthesizeAnalysis", "WriteReport"}


class ExecutionPlanner:
    """Converts Business DAG → Execution DAG.

    Usage:
        planner = ExecutionPlanner(capability_registry)
        exec_dag = planner.plan(business_dag, datasources_info)
    """

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

    def plan(
        self,
        business_dag: BusinessDAG,
        datasources_info: list[dict[str, Any]] | None = None,
    ) -> ExecutionDAG:
        """Convert Business DAG to Execution DAG.

        For each Business Task:
          1. Look up its name in BUSINESS_TASK_CAPABILITIES.
          2. Query CapabilityRegistry for matching workers.
          3. Create one ExecutionTask per available worker.

        Args:
            business_dag: The business plan from Report Planner Agent.
            datasources_info: Optional list of available data source metadata.

        Returns:
            An ExecutionDAG ready for the Execution Runtime.
        """
        if datasources_info is None:
            datasources_info = []

        exec_dag = ExecutionDAG(title=business_dag.title)

        for bt in business_dag.tasks.values():
            if bt.name in NON_EXECUTABLE_TASKS:
                logger.info("  Skipping non-executable task %s (%s)", bt.id, bt.name)
                continue

            # Get required capabilities for this business task
            capabilities = BUSINESS_TASK_CAPABILITIES.get(bt.name) or BUSINESS_TASK_CAPABILITIES["default"]

            # Match against available workers
            matched = False
            for cap in capabilities:
                workers = self._registry.get_workers(cap)
                if not workers:
                    continue

                for worker in workers:
                    task = ExecutionTask(
                        task_id=f"{bt.id}__{worker.name}",
                        business_task_id=bt.id,
                        capability=cap,
                        name=f"{bt.name}/{worker.name}",
                        params={**bt.input, "datasource_id": self._pick_datasource(datasources_info, cap)},
                        dependencies=bt.dependencies,
                    )
                    exec_dag.add(task)
                    matched = True
                    logger.info("  Mapped %s → %s (capability=%s)", bt.id, worker.name, cap)
                    break  # one task per capability is enough
                if matched:
                    break

            if not matched:
                logger.warning("  No worker found for %s (capabilities=%s)", bt.id, capabilities)

        return exec_dag

    @staticmethod
    def _pick_datasource(datasources: list[dict], capability: str) -> str:
        """Pick the best matching data source for a capability."""
        for ds in datasources:
            if capability in ds.get("capabilities", []):
                return ds.get("datasource_id", "")
        # fallback: first matching type
        type_map = {"sql": "mysql", "search": "web", "pdf": "file", "api": "rest"}
        expected_type = type_map.get(capability, "")
        for ds in datasources:
            if ds.get("datasource_type", "") == expected_type:
                return ds.get("datasource_id", "")
        return ""
