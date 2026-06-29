"""SQL Worker — executes SQL queries and returns List[Evidence].

Registered as capability ``sql`` in CapabilityRegistry.
Used by ExecutionRuntime when the Planner generates SQL tasks.
"""

from __future__ import annotations

import logging
from typing import Any

from app.gateway.models.evidence import Content, Evidence, SourceInfo, TableContent
from app.gateway.services_v1.db_utils import execute_sql
from app.gateway.workers.base import BaseWorker, ExecutionTask

logger = logging.getLogger(__name__)


class SQLWorker(BaseWorker):
    """Execute SQL queries and return results as Evidence."""

    name: str = "sql"
    capability: str = "sql"

    async def execute(self, task: ExecutionTask, context: dict[str, Any]) -> list[Evidence]:
        params = task.params
        sql = params.get("sql", "")
        metadata = params.get("datasource_metadata", context.get("datasource_metadata", {}))
        purpose = params.get("purpose", task.name)

        if not sql:
            return [
                Evidence(
                    type="sql_row",
                    source=SourceInfo(datasource_type="sql"),
                    content=Content(text="错误：未提供 SQL 查询语句"),
                    score=0.0,
                )
            ]

        try:
            result = await execute_sql(sql, metadata)
            error = result.get("error")
            columns = result.get("columns", [])
            rows = result.get("rows", [])
            row_count = result.get("row_count", 0)

            if error:
                return [
                    Evidence(
                        type="sql_row",
                        source=SourceInfo(datasource_type="sql"),
                        content=Content(text=f"SQL 执行失败: {error}"),
                        metadata={"sql": sql, "purpose": purpose},
                        score=0.0,
                    )
                ]

            # Convert to structured evidence
            str_rows = [[str(v) for v in row] for row in rows]
            text_preview = (
                f"查询 [{purpose}]: {row_count} 条结果\n"
                f"字段: {', '.join(columns[:10])}\n"
                f"示例: {str_rows[0] if str_rows else '空'}"
            )

            return [
                Evidence(
                    type="sql_row",
                    source=SourceInfo(
                        datasource_type="sql",
                        table=params.get("table", ""),
                    ),
                    content=Content(
                        text=text_preview,
                        table=TableContent(columns=columns, rows=str_rows),
                    ),
                    metadata={
                        "sql": sql,
                        "purpose": purpose,
                        "row_count": row_count,
                        "columns": columns,
                    },
                    score=1.0,
                )
            ]

        except Exception as e:
            logger.exception("SQLWorker 执行失败")
            return [
                Evidence(
                    type="sql_row",
                    source=SourceInfo(datasource_type="sql"),
                    content=Content(text=f"SQL 执行异常: {e}"),
                    metadata={"sql": sql, "purpose": purpose},
                    score=0.0,
                )
            ]

    async def validate(self, task: ExecutionTask) -> list[str]:
        warnings: list[str] = []
        if "sql" not in task.params and "datasource_id" not in task.params:
            warnings.append("缺少 sql 或 datasource_id 参数")
        return warnings
