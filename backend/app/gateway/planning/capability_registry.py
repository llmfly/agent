"""Capability Registry — maps Capability → Worker → Tool → DataSource.

Central registry that Execution Planner queries to resolve
Business Tasks into Execution Tasks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.gateway.workers.base import BaseWorker

logger = logging.getLogger(__name__)


@dataclass
class DataSourceInfo:
    """DataSource metadata available to the registry."""

    datasource_id: str = ""
    datasource_type: str = ""       # mysql, pdf, web, api, ...
    capabilities: list[str] = field(default_factory=list)


class CapabilityRegistry:
    """Central registry: Capability → [Worker, ...].

    Execution Planner queries this to find which Workers can fulfill
    a given capability for a given data source type.
    """

    def __init__(self) -> None:
        self._workers: dict[str, BaseWorker] = {}              # worker_name → worker
        self._capability_map: dict[str, list[str]] = {}        # capability → [worker_names]

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_worker(self, worker: BaseWorker) -> None:
        """Register a worker by its capability tag."""
        self._workers[worker.name] = worker
        cap = worker.capability
        if cap not in self._capability_map:
            self._capability_map[cap] = []
        if worker.name not in self._capability_map[cap]:
            self._capability_map[cap].append(worker.name)
        logger.info("Registered worker %s for capability %s", worker.name, cap)

    def register_workers(self, workers: list[BaseWorker]) -> None:
        for w in workers:
            self.register_worker(w)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def get_workers(self, capability: str) -> list[BaseWorker]:
        """Get all workers that provide a given capability."""
        names = self._capability_map.get(capability, [])
        return [self._workers[n] for n in names if n in self._workers]

    def has_capability(self, capability: str) -> bool:
        return capability in self._capability_map and bool(self._capability_map[capability])

    def list_capabilities(self) -> list[str]:
        return list(self._capability_map.keys())

    def get_worker(self, name: str) -> BaseWorker | None:
        return self._workers.get(name)

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    @property
    def worker_count(self) -> int:
        return len(self._workers)

    @property
    def capability_count(self) -> int:
        return len(self._capability_map)

    def summary(self) -> str:
        lines = ["CapabilityRegistry:"]
        for cap, names in sorted(self._capability_map.items()):
            lines.append(f"  {cap}: {', '.join(names)}")
        return "\n".join(lines)


# Module-level singleton
_registry: CapabilityRegistry | None = None


def get_capability_registry() -> CapabilityRegistry:
    global _registry
    if _registry is None:
        _registry = CapabilityRegistry()
    return _registry


def set_capability_registry(registry: CapabilityRegistry) -> None:
    global _registry
    _registry = registry
