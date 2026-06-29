"""Execution Runtime — schedules and runs Execution DAGs.

Pure DAG executor: no business logic, no data source awareness.
Only knows: schedule, retry, parallelize, checkpoint.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.gateway.models.evidence import Evidence, EvidenceGraph
from app.gateway.workers.base import BaseWorker, ExecutionDAG, ExecutionTask

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Result of a single task execution."""

    task_id: str
    success: bool
    evidence: list[Evidence] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0
    retry_count: int = 0


@dataclass
class RunReport:
    """Summary report of an entire DAG execution."""

    dag_title: str = ""
    total_tasks: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    total_duration_ms: float = 0.0
    task_results: dict[str, TaskResult] = field(default_factory=dict)
    start_time: str = ""
    end_time: str = ""

    @property
    def all_evidence(self) -> list[Evidence]:
        evs: list[Evidence] = []
        for r in self.task_results.values():
            if r.success:
                evs.extend(r.evidence)
        return evs

    def to_dict(self) -> dict[str, Any]:
        return {
            "dag_title": self.dag_title,
            "total_tasks": self.total_tasks,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped": self.skipped,
            "total_duration_ms": self.total_duration_ms,
        }


class ExecutionRuntime:
    """Pure DAG executor.

    Only responsibility: schedule tasks, retry on failure, enforce
    concurrency limits, respect timeouts, and checkpoint results.

    Does NOT know:
    - What the tasks mean (business semantics)
    - Which data sources exist
    - How to resolve capabilities
    """

    def __init__(
        self,
        worker_map: dict[str, BaseWorker],
        max_concurrency: int = 4,
        enable_checkpoint: bool = True,
    ) -> None:
        self._worker_map = worker_map
        self._max_concurrency = max_concurrency
        self._enable_checkpoint = enable_checkpoint

    async def execute(
        self,
        dag: ExecutionDAG,
        context: dict[str, Any] | None = None,
    ) -> RunReport:
        """Execute the full Execution DAG.

        Args:
            dag: The DAG to execute.
            context: Shared context (assembled by ContextManager).

        Returns:
            RunReport with all results.
        """
        if context is None:
            context = {}

        report = RunReport(dag_title=dag.title, start_time=datetime.now(timezone.utc).isoformat())
        levels = dag.get_levels()

        logger.info(
            "[Runtime] Executing DAG '%s': %d tasks in %d levels",
            dag.title, len(dag.tasks), len(levels),
        )

        for level_idx, level in enumerate(levels):
            logger.info("  [Runtime] Level %d: %d tasks", level_idx, len(level))

            semaphore = asyncio.Semaphore(self._max_concurrency)

            async def run_one(task: ExecutionTask) -> TaskResult:
                async with semaphore:
                    return await self._run_task_once(task, context)

            results = await asyncio.gather(
                *[run_one(t) for t in level],
                return_exceptions=False,
            )

            for result in results:
                report.task_results[result.task_id] = result
                if result.success:
                    report.succeeded += 1
                else:
                    report.failed += 1

                if self._enable_checkpoint:
                    self._checkpoint(task_id=result.task_id, success=result.success)

        report.total_tasks = len(dag.tasks)
        report.end_time = datetime.now(timezone.utc).isoformat()
        report.total_duration_ms = self._compute_duration(report.start_time, report.end_time)

        logger.info(
            "[Runtime] DAG '%s' done: %d succeeded, %d failed",
            dag.title, report.succeeded, report.failed,
        )
        return report

    async def _run_task_once(self, task: ExecutionTask, context: dict[str, Any]) -> TaskResult:
        """Execute a single task with retry logic."""
        worker = self._worker_map.get(task.name.split("/")[-1] if "/" in task.name else task.capability)
        if not worker:
            # Try capability-based lookup
            for w in self._worker_map.values():
                if w.capability == task.capability:
                    worker = w
                    break

        if not worker:
            return TaskResult(
                task_id=task.task_id,
                success=False,
                error=f"No worker found for capability {task.capability}",
            )

        start = datetime.now(timezone.utc)
        last_error: str | None = None

        for attempt in range(task.max_retries + 1):
            try:
                evidence = await asyncio.wait_for(
                    worker.execute(task, context),
                    timeout=task.timeout_seconds,
                )
                duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                logger.info("    [Task %s] OK (%d evidence) in %.0fms", task.task_id, len(evidence), duration)
                return TaskResult(
                    task_id=task.task_id,
                    success=True,
                    evidence=evidence,
                    duration_ms=duration,
                    retry_count=attempt,
                )
            except asyncio.TimeoutError:
                last_error = f"Timeout after {task.timeout_seconds}s"
                logger.warning("    [Task %s] attempt %d: %s", task.task_id, attempt + 1, last_error)
            except Exception as e:
                last_error = str(e)
                logger.warning("    [Task %s] attempt %d failed: %s", task.task_id, attempt + 1, last_error)

        duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        return TaskResult(
            task_id=task.task_id,
            success=False,
            error=last_error,
            duration_ms=duration,
            retry_count=task.max_retries,
        )

    @staticmethod
    def _checkpoint(task_id: str, success: bool) -> None:
        """Persist task result (stub — replace with real DB/fs)."""
        pass

    @staticmethod
    def _compute_duration(start: str, end: str) -> float:
        """Compute milliseconds between two ISO timestamps."""
        try:
            from datetime import datetime
            s = datetime.fromisoformat(start)
            e = datetime.fromisoformat(end)
            return (e - s).total_seconds() * 1000
        except Exception:
            return 0.0
