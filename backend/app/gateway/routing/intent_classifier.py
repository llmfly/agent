"""Intent classifier — identifies user intent for routing.

Phase 1: Keyword-based classifier (migrated from V1's ``_detect_report_intent``).
Later phases will add an LLM-based layer for fuzzy / compound intent.

Intent Routing Architecture (target):

```
User → Intent Router
         ├─ REPORT   → Workflow Runtime → ReportPipeline
         ├─ RESEARCH → Workflow Runtime → DeepResearchPipeline
         ├─ ANALYSIS → Workflow Runtime → AnalysisPipeline
         ├─ SKILL    → SkillRuntime
         ├─ WORKFLOW → Workflow Runtime (custom)
         └─ CHAT     → ChatAgent (Lead Agent)
```

Phase 1 only classifies — routing dispatch is added in a follow-up.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── Intent types ─────────────────────────────────────────────────────────


class IntentType(str, Enum):
    """Supported intent types for routing."""

    CHAT = "chat"
    REPORT = "report"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    SKILL = "skill"
    WORKFLOW = "workflow"


# ── Classification result ────────────────────────────────────────────────


@dataclass
class IntentResult:
    """Result of intent classification."""

    intent: IntentType
    confidence: float  # 0.0 — 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


# ── Classifier interface ─────────────────────────────────────────────────


class IntentClassifier(ABC):
    """Abstract intent classifier.

    Implementations should be stateless and thread-safe.
    """

    @abstractmethod
    def classify(self, user_message: str, context: dict[str, Any] | None = None) -> IntentResult:
        """Classify the user's intent.

        Args:
            user_message: The raw user message (before any instruction prepending).
            context: Optional runtime context (datasource info, etc.).

        Returns:
            An IntentResult with the best-guess intent.
        """
        ...


# ── Keyword-based classifier (Layer 1) ────────────────────────────────────


class KeywordIntentClassifier(IntentClassifier):
    """Fast keyword-based intent classification.

    Uses exact substring matching against known Chinese keywords.
    No LLM call, sub-millisecond latency.

    Priority-ordered: the first matching pattern wins.
    """

    # (keywords, intent, confidence, reason_template)
    PATTERNS: list[tuple[list[str], IntentType, float, str]] = [
        (
            [
                "生成报告", "分析报告", "出报告", "导出文档", "做一份报告",
                "生成文档", "解析文档", "总结文档", "分析文档", "文档总结",
                "总结汇报", "给出报告",
            ],
            IntentType.REPORT,
            0.9,
            "Keyword match: report-related terms ('{kw}')",
        ),
    ]

    def classify(self, user_message: str, context: dict[str, Any] | None = None) -> IntentResult:
        msg = user_message.lower()
        for keywords, intent, confidence, reason_tpl in self.PATTERNS:
            for kw in keywords:
                if kw in msg:
                    return IntentResult(
                        intent=intent,
                        confidence=confidence,
                        reason=reason_tpl.format(kw=kw),
                    )
        return IntentResult(
            intent=IntentType.CHAT,
            confidence=0.0,
            reason="No keyword pattern matched",
        )


# ── Multi-layer classifier ────────────────────────────────────────────────


class MultiLayerIntentClassifier(IntentClassifier):
    """Multi-layer intent classification.

    Layer 1 (fast path): keyword matching — sub-ms, no LLM call.
    Layer 2 (fuzzy path): LLM few-shot — ~200ms, for compound / unclear intents.
    Layer 3 (fallback):  CHAT — safe default when all layers are uncertain.

    Phase 1: Only Layer 1 is active.  Layers 2-3 are structure placeholders.
    """

    def __init__(self, keyword_classifier: IntentClassifier | None = None) -> None:
        self._keyword = keyword_classifier or KeywordIntentClassifier()

    def classify(self, user_message: str, context: dict[str, Any] | None = None) -> IntentResult:
        # Layer 1: Keyword matching (fast path)
        result = self._keyword.classify(user_message, context)
        if result.confidence >= 0.9:
            logger.debug(
                "IntentRouter[L1]: %s (confidence=%.2f, reason=%s)",
                result.intent.value, result.confidence, result.reason,
            )
            return result

        # Layer 2: LLM classification (placeholder — not yet implemented)
        # if result.confidence >= 0.3:
        #     return self._llm_layer(user_message, context, result)

        # Layer 3: Fallback to CHAT
        logger.debug(
            "IntentRouter[L3]: fallback to CHAT (L1=%s confidence=%.2f)",
            result.intent.value, result.confidence,
        )
        return IntentResult(
            intent=IntentType.CHAT,
            confidence=0.0,
            reason="Fallback to CHAT after all layers",
        )
