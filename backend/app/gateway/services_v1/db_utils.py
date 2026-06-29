"""Database utility functions extracted from the old ReportWorkflow.

Shared helpers used by SQL Worker, DataSource plugins, and the pipeline.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def connect_mysql(metadata: dict):
    """Create a synchronous pymysql connection."""
    import pymysql
    return pymysql.connect(
        host=metadata.get("host", "localhost"),
        port=metadata.get("port", 3306),
        user=metadata.get("username", ""),
        password=metadata.get("password", ""),
        database=metadata.get("database", ""),
        charset="utf8mb4",
        connect_timeout=5,
    )


def fetch_all_table_names(metadata: dict) -> list[str]:
    """Get all table names from database."""
    conn = connect_mysql(metadata)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def fetch_schema_for_tables(metadata: dict, table_names: list[str]) -> str:
    """Fetch DDL + stats only for the given tables."""
    if not table_names:
        return ""
    conn = connect_mysql(metadata)
    try:
        with conn.cursor() as cursor:
            parts = []
            for tname in table_names:
                cursor.execute(f"SHOW FULL COLUMNS FROM `{tname}`")
                cols = cursor.fetchall()
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM `{tname}`")
                    row_count = cursor.fetchone()[0] or 0
                except Exception:
                    row_count = 0
                parts.append(f"### {tname} (行数:~{row_count})")
                for c in cols:
                    desc = f"  - {c[0]} ({c[1]})"
                    if c[4] == "PRI":
                        desc += " [PK]"
                    if c[8]:
                        desc += f"  -- {c[8]}"
                    parts.append(desc)
                parts.append("")
            return "\n".join(parts) or "（无表）"
    finally:
        conn.close()


def get_ddl_for_table(schema_text: str, table_name: str) -> str:
    """Extract DDL for a specific table from full schema text."""
    lines = []
    in_target = False
    for line in schema_text.splitlines():
        if line.startswith(f"### {table_name}"):
            in_target = True
        elif line.startswith("### ") and in_target:
            break
        if in_target:
            lines.append(line)
    return "\n".join(lines) if lines else schema_text


def check_sql_safety(sql: str, ddl: str, table_name: str) -> list[str]:
    """Basic static SQL validation — detect obvious issues before execution."""
    warnings: list[str] = []

    if table_name and table_name not in sql:
        warnings.append(f"SQL 中没有引用目标表 `{table_name}`")

    dangerous = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "CREATE"]
    for kw in dangerous:
        if re.search(rf"\b{kw}\b", sql, re.IGNORECASE):
            warnings.append(f"SQL 包含危险关键词: {kw}")

    if ddl:
        col_pattern = re.compile(r"^\s*-\s+`?(\w+)`?", re.MULTILINE)
        ddl_cols = set(col_pattern.findall(ddl))
        sql_cols_raw = set(re.findall(r"`(\w+)`", sql))
        as_aliases = set(re.findall(r"\bAS\s+`(\w+)`", sql, re.IGNORECASE))
        table_refs = set(re.findall(r"\b(?:FROM|JOIN)\s+`(\w+)`", sql, re.IGNORECASE))
        sql_cols = sql_cols_raw - as_aliases - table_refs
        unknown = sql_cols - ddl_cols
        if unknown and ddl_cols:
            keywords = {"LIMIT", "AS", "DESC", "ASC", "COUNT", "SUM", "AVG", "MAX", "MIN",
                        "DISTINCT", "ORDER", "GROUP", "BY", "FROM", "WHERE", "HAVING",
                        "JOIN", "ON", "AND", "OR", "IN", "NOT", "NULL", "IS", "LIKE",
                        "BETWEEN", "EXISTS", "UNION", "ALL", "ANY", "SOME"}
            actual_unknown = {c for c in unknown if c.upper() not in keywords}
            if actual_unknown:
                warnings.append(f"SQL 引用了 DDL 中不存在的字段: {', '.join(actual_unknown)}")

    return warnings


async def execute_sql(sql: str, metadata: dict, limit: int = 2000) -> dict[str, Any]:
    """Execute a SQL query and return structured results."""
    from sqlalchemy import text as sql_text
    from sqlalchemy.ext.asyncio import create_async_engine
    from urllib.parse import quote

    url = (
        f"mysql+aiomysql://{quote(metadata.get('username', ''))}"
        f":{quote(metadata.get('password', ''))}"
        f"@{metadata.get('host', 'localhost')}"
        f":{metadata.get('port', 3306)}"
        f"/{metadata.get('database', '')}"
    )

    engine = create_async_engine(url, echo=False)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(sql_text(sql))
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchmany(limit)]
            return {"generated_query": sql, "columns": columns, "rows": rows, "row_count": len(rows)}
    except Exception as e:
        return {"generated_query": sql, "columns": [], "rows": [], "row_count": 0, "error": str(e)}
    finally:
        await engine.dispose()


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = re.sub(r"[^\w\s\u4e00-\u9fff-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text[:100] or "report"
