"""Schema Store with embedding-based retrieval.

Instead of dumping all 300+ tables into the prompt, uses embedding similarity
to retrieve only the Top-K most relevant tables for a given question.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ColumnSchema:
    """A single column in a table."""
    name: str
    dtype: str
    nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    ref_table: str | None = None
    ref_column: str | None = None
    comment: str | None = None
    has_index: bool = False
    sample_values: list[str] = field(default_factory=list)
    enum_values: list[str] | None = None


@dataclass
class TableSchema:
    """Schema for a single table."""
    name: str
    columns: list[ColumnSchema]
    row_count: int = 0
    description: str = ""

    @property
    def signature(self) -> str:
        """Compact signature for embedding — includes column comments for better semantic matching."""
        cols = ", ".join(
            f"{c.name}({c.dtype}){' -- ' + c.comment if c.comment else ''}"
            for c in self.columns[:20]
        )
        desc = f" ({self.description})" if self.description else ""
        return f"{self.name}{desc}({cols})"

    @property
    def ddl(self) -> str:
        """Full DDL-like description for prompt."""
        lines = [f"### 表: {self.name}  (行数: ~{self.row_count})"]
        for c in self.columns:
            nullable = "NULL" if c.nullable else "NOT NULL"
            pk = " PK" if c.is_primary_key else ""
            fk = f" → {c.ref_table}.{c.ref_column}" if c.is_foreign_key and c.ref_table else ""
            comment = f"  -- {c.comment}" if c.comment else ""
            enum = f" [{','.join(c.enum_values)}]" if c.enum_values else ""
            sample_info = ""
            if c.sample_values:
                sv_str = ", ".join(str(v)[:20] for v in c.sample_values[:5])
                sample_info = f"  示例值: [{sv_str}]"
            lines.append(f"  - {c.name} ({c.dtype}, {nullable}){pk}{fk}{enum}{comment}{sample_info}")
        return "\n".join(lines)

    @property
    def summary(self) -> str:
        """One-line summary for schema retrieval display."""
        return f"{self.name}({', '.join(c.name for c in self.columns[:10])})"


def _build_column_hash(table_name: str, col_name: str) -> str:
    """Deterministic hash for column-level dedup."""
    return hashlib.md5(f"{table_name}.{col_name}".encode()).hexdigest()[:16]


class SchemaStore:
    """Schema store with embedding-based table retrieval.

    Usage:
        store = SchemaStore()
        await store.load_from_mysql(metadata)
        relevant = await store.retrieve("查询学生成绩", top_k=5)
    """

    def __init__(self) -> None:
        self._tables: list[TableSchema] = []
        self._table_map: dict[str, TableSchema] = {}
        # Embedding cache: column hash -> embedding vector
        self._embeddings: dict[str, list[float]] = {}
        self._embedder = None

    async def load_from_mysql(self, metadata: dict[str, Any]) -> None:
        """Discover and load schema from MySQL using pymysql."""
        import pymysql

        conn = pymysql.connect(
            host=metadata.get("host", "localhost"),
            port=metadata.get("port", 3306),
            user=metadata.get("username", ""),
            password=metadata.get("password", ""),
            database=metadata.get("database", ""),
            charset="utf8mb4",
            connect_timeout=5,
        )

        try:
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                all_table_names = [row[0] for row in cursor.fetchall()]

                # Filter by selected tables in metadata if specified
                user_tables = metadata.get("tables")
                if user_tables and isinstance(user_tables, list):
                    table_names = [t for t in all_table_names if t in user_tables]
                else:
                    table_names = all_table_names

                if not table_names:
                    logger.warning("No tables found in database after filtering")
                    return

                # Pre-fetch FK info for all tables
                fk_map: dict[str, dict[str, tuple[str, str]]] = {}
                for tname in table_names:
                    try:
                        cursor.execute(
                            f"SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
                            f"FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
                            f"WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND REFERENCED_TABLE_NAME IS NOT NULL",
                            (metadata.get("database", ""), tname),
                        )
                        fk_map[tname] = {r[0]: (r[1], r[2]) for r in cursor.fetchall()}
                    except Exception:
                        fk_map[tname] = {}

                for tname in table_names:
                    cursor.execute(f"SHOW FULL COLUMNS FROM `{tname}`")
                    raw_cols = cursor.fetchall()
                    fks = fk_map.get(tname, {})

                    # Row count
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM `{tname}`")
                        row_count = cursor.fetchone()[0] or 0
                    except Exception:
                        row_count = 0

                    columns = []
                    for raw in raw_cols:
                        col_name = raw[0]
                        col_type = raw[1]
                        nullable = raw[3] == "YES"
                        is_pk = raw[4] == "PRI"
                        comment = raw[8] or ""

                        ref_table, ref_col = fks.get(col_name, (None, None))

                        # Sample values (first 3 distinct values)
                        sample = []
                        try:
                            cursor.execute(f"SELECT DISTINCT `{col_name}` FROM `{tname}` WHERE `{col_name}` IS NOT NULL LIMIT 3")
                            sample = [str(r[0]) for r in cursor.fetchall()]
                        except Exception:
                            pass

                        # Enum detection
                        enum_values = None
                        enum_match = re.match(r"enum\((.+)\)", col_type, re.IGNORECASE)
                        if enum_match:
                            enum_values = [v.strip("'\" ") for v in enum_match.group(1).split(",")]

                        columns.append(ColumnSchema(
                            name=col_name,
                            dtype=col_type,
                            nullable=nullable,
                            is_primary_key=is_pk,
                            is_foreign_key=ref_table is not None,
                            ref_table=ref_table,
                            ref_column=ref_col,
                            comment=comment,
                            has_index=raw[4] == "MUL",
                            sample_values=sample,
                            enum_values=enum_values,
                        ))

                    table = TableSchema(name=tname, columns=columns, row_count=row_count)
                    self._tables.append(table)
                    self._table_map[tname] = table

            logger.info("Schema loaded: %d tables", len(self._tables))

        finally:
            conn.close()

    async def load_from_dict(self, tables: list[dict]) -> None:
        """Load schema from a dict (useful for testing or non-MySQL sources)."""
        for t in tables:
            columns = [ColumnSchema(**c) for c in t.get("columns", [])]
            table = TableSchema(
                name=t["name"],
                columns=columns,
                row_count=t.get("row_count", 0),
                description=t.get("description", ""),
            )
            self._tables.append(table)
            self._table_map[table.name] = table

    async def _ensure_embedder(self) -> Any:
        """Lazy-init the embedding model."""
        if self._embedder is None:
            # Use a lightweight local embedding for schema retrieval
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            except ImportError:
                logger.warning("sentence-transformers not installed; using simple keyword overlap")
                self._embedder = "keyword"
        return self._embedder

    @staticmethod
    def _keyword_score(question: str, table: TableSchema) -> float:
        """Simple keyword overlap score when no embedding model available."""
        q_words = set(re.findall(r"\w+", question.lower()))
        t_words = set()
        t_words.add(table.name.lower())
        for c in table.columns:
            t_words.add(c.name.lower())
            if c.comment:
                for w in re.findall(r"\w+", c.comment.lower()):
                    t_words.add(w)
        if not q_words or not t_words:
            return 0.0
        overlap = len(q_words & t_words)
        return overlap / max(len(q_words), 1)

    async def retrieve(self, question: str, top_k: int = 5) -> list[TableSchema]:
        """Retrieve Top-K most relevant tables for a question."""
        embedder = await self._ensure_embedder()

        if embedder == "keyword":
            scored = [(self._keyword_score(question, t), t) for t in self._tables]
        else:
            # Embedding-based retrieval
            q_emb = embedder.encode(question, normalize_embeddings=True)
            table_sigs = [t.signature for t in self._tables]
            t_embs = embedder.encode(table_sigs, normalize_embeddings=True)
            import numpy as np
            scores = np.dot(t_embs, q_emb)
            scored = list(zip(scores, self._tables))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        logger.info("Schema retrieval: %s -> %s", question[:50], [t[1].name for t in top])
        return [t[1] for t in top]

    def get_table(self, name: str) -> TableSchema | None:
        """Get a single table by name."""
        return self._table_map.get(name)

    @property
    def all_tables(self) -> list[TableSchema]:
        return self._tables

    @property
    def total_tables(self) -> int:
        return len(self._tables)
