"""Few-shot Store — retrieves similar SQL examples via embedding similarity.

Completely generic — all examples are pure SQL pattern examples with
no domain-specific table names. Works for ANY database schema.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FewShotExample:
    """A single few-shot example — uses generic placeholders for table/column names."""
    question: str
    sql: str
    tags: list[str] = field(default_factory=list)


# ── Pure SQL pattern examples (no domain-specific table names) ────
# Every example uses placeholders like `table_name`, `field`, `col`
# so they are valid for ANY database.

_GENERIC_EXAMPLES: list[FewShotExample] = [
    FewShotExample(
        question="统计表中的总记录数",
        sql="SELECT COUNT(*) AS `total` FROM `table_name`",
        tags=["count", "basic"],
    ),
    FewShotExample(
        question="按某个字段分组并统计每组数量",
        sql="SELECT `group_field`, COUNT(*) AS `count` FROM `table_name` GROUP BY `group_field` ORDER BY `count` DESC",
        tags=["count", "group_by", "order_by"],
    ),
    FewShotExample(
        question="多表关联查询",
        sql="SELECT a.`col1`, b.`col2` FROM `table_a` a JOIN `table_b` b ON a.`id` = b.`ref_id` WHERE a.`status` = 1",
        tags=["join", "filter"],
    ),
    FewShotExample(
        question="按值排序取前N条",
        sql="SELECT `col1`, `col2` FROM `table_name` WHERE `col1` IS NOT NULL ORDER BY `col2` DESC LIMIT 10",
        tags=["order_by", "top_k", "filter"],
    ),
    FewShotExample(
        question="按条件过滤并分组统计",
        sql="SELECT `group_field`, AVG(`value_field`) AS `avg_value`, COUNT(*) AS `count` FROM `table_name` WHERE `status` = 'active' GROUP BY `group_field`",
        tags=["filter", "avg", "count", "group_by"],
    ),
    FewShotExample(
        question="查找没有关联记录的数据（LEFT JOIN + IS NULL）",
        sql="SELECT a.* FROM `table_a` a LEFT JOIN `table_b` b ON a.`id` = b.`ref_id` WHERE b.`id` IS NULL",
        tags=["left_join", "anti_join", "filter"],
    ),
    FewShotExample(
        question="按字段分组后取每组的聚合值",
        sql="SELECT `group_field`, MAX(`value_field`) AS `max_val`, MIN(`value_field`) AS `min_val` FROM `table_name` GROUP BY `group_field`",
        tags=["max", "min", "group_by"],
    ),
    FewShotExample(
        question="按日期范围过滤并统计",
        sql="SELECT `category`, COUNT(*) AS `count`, SUM(`amount`) AS `total` FROM `table_name` WHERE `created_at` >= '2026-01-01' AND `created_at` < '2026-07-01' GROUP BY `category` ORDER BY `total` DESC",
        tags=["date_filter", "sum", "count", "group_by"],
    ),
    FewShotExample(
        question="去重统计",
        sql="SELECT COUNT(DISTINCT `field_name`) AS `unique_count` FROM `table_name`",
        tags=["distinct", "count"],
    ),
    FewShotExample(
        question="关联多张表并聚合",
        sql="SELECT a.`group_field`, COUNT(DISTINCT b.`id`) AS `count`, SUM(c.`amount`) AS `total` FROM `table_a` a JOIN `table_b` b ON a.`id` = b.`a_id` JOIN `table_c` c ON b.`id` = c.`b_id` WHERE a.`status` = 1 GROUP BY a.`group_field` HAVING `count` > 5 ORDER BY `total` DESC LIMIT 20",
        tags=["multi_join", "count", "sum", "group_by", "having", "filter"],
    ),
    FewShotExample(
        question="求字段总和和平均值",
        sql="SELECT SUM(`amount`) AS `total_amount`, AVG(`amount`) AS `avg_amount` FROM `table_name` WHERE `amount` IS NOT NULL",
        tags=["sum", "avg"],
    ),
]


class FewShotStore:
    """Few-shot example store with embedding-based retrieval.

    Only contains pure SQL pattern examples — no domain-specific
    table names. Works for ANY database.
    """

    def __init__(self) -> None:
        self._examples: list[FewShotExample] = list(_GENERIC_EXAMPLES)
        self._embedder = None
        self._embeddings: list[list[float]] = []

    def add_example(self, example: FewShotExample) -> None:
        """Add a new example (from user feedback / corrected queries)."""
        self._examples.append(example)
        self._embeddings = []

    async def _ensure_embedder(self) -> Any:
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            except ImportError:
                self._embedder = "keyword"
        return self._embedder

    async def retrieve(self, question: str, top_k: int = 3) -> list[FewShotExample]:
        """Retrieve Top-K most similar examples by embedding similarity."""
        if not self._examples:
            return []

        embedder = await self._ensure_embedder()
        ex_questions = [e.question for e in self._examples]

        if embedder == "keyword":
            q_words = set(re.findall(r"\w+", question.lower()))
            scored = []
            for i, ex in enumerate(self._examples):
                ex_words = set(re.findall(r"\w+", ex.question.lower()))
                overlap = len(q_words & ex_words) if q_words else 0
                scored.append((overlap, i))
            scored.sort(key=lambda x: x[0], reverse=True)
        else:
            import numpy as np
            q_emb = embedder.encode(question, normalize_embeddings=True)
            if not self._embeddings or len(self._embeddings) != len(self._examples):
                ex_embs = embedder.encode(ex_questions, normalize_embeddings=True)
                self._embeddings = [list(e) for e in ex_embs]
            scores = np.dot(self._embeddings, q_emb)
            scored = [(scores[i], i) for i in range(len(self._examples))]

        scored.sort(key=lambda x: x[0], reverse=True)
        return [self._examples[i] for _, i in scored[:top_k]]
