"""Context Manager — unified context assembly for Workers.

Workers do NOT retrieve context directly. They receive a pre-assembled
context dict from the ContextManager, containing all the information
they need (memory, knowledge, conversation, environment).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RuntimeContext:
    """Unified context for a single DAG execution.

    Assembled by ContextManager before ExecutionRuntime starts.
    Passed to every Worker as the `context` parameter.
    """

    conversation_id: str = ""
    user_id: str = ""
    thread_id: str = ""

    # System context
    memory: dict[str, Any] = field(default_factory=dict)
    knowledge: list[dict[str, Any]] = field(default_factory=list)
    environment: dict[str, Any] = field(default_factory=dict)

    # Data source credentials (resolved, never raw secrets)
    datasource_credentials: dict[str, dict[str, Any]] = field(default_factory=dict)

    # User query + conversation history
    user_query: str = ""
    conversation_history: list[dict[str, str]] = field(default_factory=list)

    # Runtime metadata
    execution_id: str = ""
    started_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "thread_id": self.thread_id,
            "memory": self.memory,
            "knowledge_count": len(self.knowledge),
            "datasource_count": len(self.datasource_credentials),
            "user_query": self.user_query[:100],
        }


class ContextManager:
    """Assembles RuntimeContext for each DAG execution.

    Responsibilities:
    - Load conversation history
    - Load user memory/preferences
    - Resolve data source credentials
    - Prepare Knowledge context
    """

    def __init__(self) -> None:
        self._memory_provider: Any = None
        self._knowledge_provider: Any = None

    async def assemble(
        self,
        *,
        user_id: str = "anonymous",
        conversation_id: str = "",
        thread_id: str = "",
        user_query: str = "",
        datasource_metadata: list[dict[str, Any]] | None = None,
    ) -> RuntimeContext:
        """Assemble runtime context for execution.

        This is called once per report generation, before the DAG runs.
        """
        ctx = RuntimeContext(
            conversation_id=conversation_id,
            user_id=user_id,
            thread_id=thread_id,
            user_query=user_query,
        )

        # Memory
        if self._memory_provider:
            try:
                ctx.memory = await self._memory_provider.get(thread_id)
            except Exception as e:
                logger.warning("Memory load failed: %s", e)

        # Data source credentials
        if datasource_metadata:
            for ds in datasource_metadata:
                ds_id = ds.get("datasource_id", "")
                if ds_id:
                    ctx.datasource_credentials[ds_id] = ds

        return ctx

    def set_memory_provider(self, provider: Any) -> None:
        self._memory_provider = provider

    def set_knowledge_provider(self, provider: Any) -> None:
        self._knowledge_provider = provider
