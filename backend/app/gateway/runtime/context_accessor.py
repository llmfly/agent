"""Context accessor — clean typed access to runtime context for tools.

Tools running inside the LangGraph graph receive a ``Runtime`` object
whose ``context`` and ``config`` dicts are populated by ``ContextBuilder``.
This module provides typed accessors so tools don't need to duplicate
the fallback logic.
"""

from __future__ import annotations

import os
import logging
from typing import Any

from deerflow.tools.types import Runtime

logger = logging.getLogger(__name__)

# ── File-type data source constants ───────────────────────────────────────

_FILE_DATA_SOURCE_TYPES = {"pdf", "docx", "txt", "xlsx", "csv"}

# ── Internal helpers ─────────────────────────────────────────────────────


def _get_configurable(cfg: dict[str, Any] | None, key: str) -> Any:
    """Read a key from the nested configurable dict (safe access)."""
    if not cfg:
        return None
    return (
        cfg.get("configurable", {}).get(key)
        or cfg.get("context", {}).get(key)
    )


# ── Public accessors ─────────────────────────────────────────────────────


def get_selected_data_sources(runtime: Runtime) -> list[dict[str, Any]]:
    """Get ``selected_data_sources`` from runtime context.

    Tries ``runtime.context`` first, then falls back to ``runtime.config``.
    """
    selected_sources: Any = None
    if runtime.context:
        selected_sources = runtime.context.get("selected_data_sources")
    if not selected_sources:
        cfg = getattr(runtime, "config", None) or {}
        selected_sources = _get_configurable(cfg, "selected_data_sources")
    return selected_sources or []


def get_thread_id(runtime: Runtime) -> str | None:
    """Get the thread/conversation ID from runtime context or config."""
    thread_id = runtime.context.get("thread_id") if runtime.context else None
    if thread_id:
        return str(thread_id)
    cfg = getattr(runtime, "config", None) or {}
    tid = _get_configurable(cfg, "thread_id")
    if tid:
        return str(tid)
    try:
        from langgraph.config import get_config
        return get_config().get("configurable", {}).get("thread_id")
    except RuntimeError:
        return None


def get_user_id(runtime: Runtime) -> str:
    """Get user ID from runtime context."""
    return runtime.context.get("user_id", "anonymous") if runtime.context else "anonymous"


def get_sql_data_sources(runtime: Runtime) -> list[dict[str, Any]]:
    """Get only SQL-type data sources from runtime context."""
    return [ds for ds in get_selected_data_sources(runtime) if ds.get("type") == "sql"]


def get_first_sql_schema_summary(runtime: Runtime) -> dict[str, Any]:
    """Get ``schema_summary`` from the first SQL data source."""
    sql_sources = get_sql_data_sources(runtime)
    if not sql_sources:
        return {}
    return sql_sources[0].get("schema_summary") or {}


def get_first_sql_metadata(runtime: Runtime) -> dict[str, Any]:
    """Get ``metadata`` from the first SQL data source."""
    sql_sources = get_sql_data_sources(runtime)
    if not sql_sources:
        return {}
    return sql_sources[0].get("metadata") or {}


def get_file_data_sources(runtime: Runtime) -> list[dict[str, Any]]:
    """Get file-type data sources with resolved ``file_path``."""
    result: list[dict[str, Any]] = []
    for ds in get_selected_data_sources(runtime):
        ds_type = ds.get("type", "")
        if ds_type not in _FILE_DATA_SOURCE_TYPES:
            continue
        meta = ds.get("metadata") or {}
        file_path = meta.get("file_path", "")
        if file_path:
            result.append({
                "name": ds.get("name", "?"),
                "type": ds_type,
                "file_path": file_path,
            })
    return result


def get_first_file_path(runtime: Runtime) -> str:
    """Get the file path of the first file-type data source."""
    file_sources = get_file_data_sources(runtime)
    if not file_sources:
        return ""
    if len(file_sources) > 1:
        logger.warning(
            "context_accessor: %d file data sources found, auto-using first",
            len(file_sources),
        )
    return file_sources[0]["file_path"]


def get_server_base_url(runtime: Runtime) -> str:
    """Get the server base URL for constructing absolute download links.

    Priority:
    1. ``SERVER_BASE_URL`` environment variable.
    2. ``runtime.config`` configurable.
    3. Fallback to empty string (relative URLs).
    """
    url = os.environ.get("SERVER_BASE_URL")
    if url:
        return url.rstrip("/")
    cfg = getattr(runtime, "config", None) or {}
    url = _get_configurable(cfg, "server_base_url")
    if url:
        return url.rstrip("/")
    return ""
