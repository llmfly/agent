"""Worker base class and ExecutionTask definition.

All Workers inherit from BaseWorker and implement the `execute` method.
Workers are stateless: same input → same output.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.gateway.models.evidence import Evidence


@dataclass
class ExecutionTask:
    """A single executable task within the Execution DAG.

    This is the atomic unit of work in the Execution Layer.
    Workers receive an ExecutionTask and return List[Evidence].
    """

    task_id: str = field(default_factory=lambda: f"et_{uuid.uuid4().hex[:8]}")
    business_task_id: str = ""                # originating Business Task ID
    capability: str = ""                      # which capability this task uses
    name: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)  # task_ids this depends on
    max_retries: int = 2
    timeout_seconds: int = 120


class BaseWorker(ABC):
    """Abstract base for all Workers.

    Workers are stateless tools with a single responsibility.
    They receive an ExecutionTask, execute, and return structured Evidence.
    """

    name: str = "base_worker"
    capability: str = ""

    @abstractmethod
    async def execute(self, task: ExecutionTask, context: dict[str, Any]) -> list[Evidence]:
        """Execute a task and return evidence.

        Args:
            task: The execution task with params.
            context: Context assembled by ContextManager (memory, knowledge, etc.).

        Returns:
            List of Evidence objects. Never None — return empty list if no results.
        """
        ...

    async def validate(self, task: ExecutionTask) -> list[str]:
        """Pre-execution validation. Return list of warning messages."""
        return []


@dataclass
class ExecutionDAG:
    """A complete execution plan — a DAG of ExecutionTasks.

    The Execution Runtime consumes this and schedules execution.
    """

    title: str = ""
    tasks: dict[str, ExecutionTask] = field(default_factory=dict)

    def add(self, task: ExecutionTask) -> None:
        self.tasks[task.task_id] = task

    def add_all(self, tasks: list[ExecutionTask]) -> None:
        for t in tasks:
            self.add(t)

    def get_roots(self) -> list[ExecutionTask]:
        """Return tasks with no dependencies."""
        return [t for t in self.tasks.values() if not t.dependencies]

    def get_levels(self) -> list[list[ExecutionTask]]:
        """Topological sort into levels for parallel execution."""
        task_map = self.tasks
        in_degree = {tid: len(t.dependencies) for tid, t in task_map.items()}
        dependents: dict[str, list[str]] = {tid: [] for tid in task_map}
        for tid, t in task_map.items():
            for dep_id in t.dependencies:
                if dep_id in dependents:
                    dependents[dep_id].append(tid)

        levels: list[list[ExecutionTask]] = []
        queue = [task_map[tid] for tid, deg in in_degree.items() if deg == 0]

        while queue:
            levels.append(list(queue))
            queue = []
            for t in levels[-1]:
                for dep in dependents[t.task_id]:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        queue.append(task_map[dep])

        unscheduled = [task_map[tid] for tid, deg in in_degree.items() if deg > 0]
        if unscheduled:
            levels.append(unscheduled)

        return levels
