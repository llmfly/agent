"""DataSource Plugins — abstract interface + concrete implementations."""

from __future__ import annotations

import abc
import logging
from typing import Any

from app.gateway.services_v1.db_utils import execute_sql, fetch_all_table_names, fetch_schema_for_tables

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Abstract Base
# ═══════════════════════════════════════════════════════════════

class DataSourcePlugin(abc.ABC):
    """Abstract data source — provides schema metadata and executes queries."""

    @abc.abstractmethod
    async def list_tables(self) -> list[str]:
        """Return all available table names."""
        ...

    @abc.abstractmethod
    async def describe(self, tables: list[str]) -> str:
        """Return DDL/schema text for the given tables."""
        ...

    @abc.abstractmethod
    async def execute(self, sql: str) -> tuple[list[str], list[list[Any]], int]:
        """Execute SQL and return (columns, rows, row_count)."""
        ...

    @classmethod
    def from_metadata(cls, metadata: dict) -> "DataSourcePlugin":
        """Factory: create the appropriate plugin from datasource metadata."""
        engine = (metadata.get("engine") or "").lower()
        if engine in ("mysql", "postgresql", "sqlite", "mssql"):
            return MySQLDataSourcePlugin(metadata)
        if metadata.get("type") == "file":
            return FileDataSourcePlugin(metadata)
        return MySQLDataSourcePlugin(metadata)


class MySQLDataSourcePlugin(DataSourcePlugin):
    """DataSource plugin for MySQL-compatible databases."""

    def __init__(self, metadata: dict) -> None:
        self._metadata = metadata

    async def list_tables(self) -> list[str]:
        return fetch_all_table_names(self._metadata)

    async def describe(self, tables: list[str]) -> str:
        return fetch_schema_for_tables(self._metadata, tables)

    async def execute(self, sql: str) -> tuple[list[str], list[list[Any]], int]:
        result = await execute_sql(sql, self._metadata)
        if result.get("error"):
            raise RuntimeError(result["error"])
        return result["columns"], result["rows"], result["row_count"]


class FileDataSourcePlugin(DataSourcePlugin):
    """DataSource plugin for file-based data (Excel/CSV read as markdown)."""

    def __init__(self, metadata: dict) -> None:
        self._metadata = metadata

    async def list_tables(self) -> list[str]:
        logger.warning("FileDataSourcePlugin: list_tables() not supported")
        return []

    async def describe(self, tables: list[str]) -> str:
        logger.warning("FileDataSourcePlugin: describe() not supported")
        return ""

    async def execute(self, sql: str) -> tuple[list[str], list[list[Any]], int]:
        raise NotImplementedError("FileDataSourcePlugin does not support SQL execution")
