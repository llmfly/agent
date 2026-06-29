import json
import logging
import re
import time
from pathlib import Path

from langchain.tools import tool

from deerflow.tools.types import Runtime

logger = logging.getLogger(__name__)

# ── In-process source cache per thread ───────────────────────────────
# Key: thread_id, Value: {"sources": list | None, "_ts": float}
# Avoids redundant DB queries on repeated LLM tool calls within the
# same 120s window. This is NOT a throttling mechanism — the tool
# is always available.
_source_cache: dict[str, dict] = {}


def _get_source_cache(thread_id: str) -> dict:
    """Get or create per-thread source cache, with auto-cleanup after 120s."""
    now = time.monotonic()
    entry = _source_cache.get(thread_id)
    if entry is None or now - entry.get("_ts", 0) > 120:
        entry = {"sources": None, "_ts": now}
        _source_cache[thread_id] = entry
        # Clean stale entries
        stale = [k for k, v in _source_cache.items() if now - v.get("_ts", 0) > 120]
        for k in stale:
            _source_cache.pop(k, None)
    return entry


# ── Report-intent detection (soft redirect, never refuse) ─────────────
_REPORT_INTENT_PATTERNS = re.compile(
    r"(报告|报表|生成.*报告|写.*报告|出.*报告|分析.*报告)"
)


def _build_schema_block(sources: list[dict]) -> str:
    """Build a human-readable schema summary from data source list."""
    schema_summaries = []
    for ds in sources:
        ss = ds.get("schema_summary") or {}
        meta = ds.get("metadata") or {}
        name = ds.get("name", "?")
        ds_type = ds.get("type", "?")
        tables = ss.get("tables", [])

        if tables:
            summary_parts = [f"📦 {name} ({ds_type})"]
            for t in tables[:10]:
                cols = ", ".join(
                    f"{c['name']}({c['type']})"
                    for c in t.get("columns", [])[:10]
                )
                rows = t.get("row_count", "?")
                summary_parts.append(f"  - {t['name']} (~{rows} 行) : {cols}")
            schema_summaries.append("\n".join(summary_parts))
        elif ds_type in ("pdf", "docx", "txt", "xlsx", "csv"):
            file_path = meta.get("file_path", "")
            doc_summary = ss.get("document_summary") or {}
            chapters = doc_summary.get("chapters") or doc_summary.get("key_topics") or []
            preview = doc_summary.get("content_preview", "")[:200]
            summary_parts = [f"📄 {name} ({ds_type})"]
            if file_path:
                summary_parts.append(f"  路径: {file_path}")
            if doc_summary.get("page_count"):
                summary_parts.append(f"  页数: {doc_summary['page_count']}")
            if chapters:
                summary_parts.append(f"  章节: {', '.join(chapters)}")
            if preview:
                summary_parts.append(f"  预览: {preview}")
            schema_summaries.append("\n".join(summary_parts))
        else:
            schema_summaries.append(f"  {name} ({ds_type})")

    return "\n".join(schema_summaries) if schema_summaries else "（无数据源）"

def _get_thread_id(runtime: Runtime) -> str | None:
    """Resolve the current conversation/thread id from runtime context."""
    thread_id = runtime.context.get("thread_id") if runtime.context else None
    if thread_id:
        return thread_id
    cfg = getattr(runtime, "config", None) or {}
    thread_id = cfg.get("configurable", {}).get("thread_id")
    if thread_id:
        return thread_id
    try:
        from langgraph.config import get_config
        return get_config().get("configurable", {}).get("thread_id")
    except RuntimeError:
        return None

def _save_query_results(runtime: Runtime, conversation_id: str, data: dict) -> Path | None:
    try:
        user_id = runtime.context.get("user_id", "anonymous") if runtime.context else "anonymous"
        base = Path.cwd()
        if base.name != "backend":
            base = base / "backend"
        workspace_dir = base / ".deer-flow" / "users" / user_id / "threads" / conversation_id / "user-data" / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        file_path = workspace_dir / "query_results.json"
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return file_path
    except Exception as e:
        logger.warning("Failed to save query results to workspace: %s", e)
        return None

@tool("query_data_source", parse_docstring=True)
async def query_data_source_tool(
    runtime: Runtime,
    query: str,
    datasource_id: str | None = None,
    datasource_name: str | None = None,
) -> str:
    """Query data from a SQL or Elasticsearch data source dynamically configured for this conversation.

    Use this tool when the user asks you to retrieve, query, count, or summarize data from their
    associated data sources (such as a database containing customs transaction records or other tables).

    Args:
        query: The natural language question or query to run. For example, "统计海关交易数据，按商品类别分组" or "查询所有的交易记录".
        datasource_id: Optional ID of the data source to query. If not provided, it will search the list of active data sources.
        datasource_name: Optional name of the data source to query. If not provided, it will search the list of active data sources.
    """
    conversation_id = _get_thread_id(runtime)

    # 1. Resolve selected data sources
    selected_sources = None

    # ── Try in-process cache first ─────────────────────────────────
    cache = _get_source_cache(conversation_id) if conversation_id else None
    if cache and cache.get("sources"):
        selected_sources = cache["sources"]
        logger.debug("query_data_source: using cached sources for thread %s", conversation_id)

    if not selected_sources:
        if runtime.context:
            selected_sources = runtime.context.get("selected_data_sources")
        if not selected_sources:
            selected_sources = runtime.config.get("configurable", {}).get("selected_data_sources")
        if not selected_sources:
            selected_sources = runtime.config.get("context", {}).get("selected_data_sources")

    # Fallback: try reading from workspace data source service
    if not selected_sources and conversation_id:
        try:
            from app.gateway.services_v1.workspace_datasource_service import workspace_datasource_service

            selected_sources = await workspace_datasource_service.get_data_sources_for_conversation(conversation_id)

            # Fallback: old v1 memory cache
            if not selected_sources:
                from app.gateway.services_v1.data_source_service import (
                    get_data_sources_for_conversation,
                    get_data_sources_for_conversation_db,
                )
                selected_sources = get_data_sources_for_conversation(conversation_id)
                if not selected_sources:
                    selected_sources = await get_data_sources_for_conversation_db(conversation_id)

            if selected_sources:
                logger.info(
                    "query_data_source: loaded %d data sources "
                    "for conversation %s (workspace/v1 fallback)",
                    len(selected_sources), conversation_id,
                )
        except ImportError:
            pass
        except Exception as e:
            logger.warning("query_data_source: fallback lookup failed: %s", e)

    if not selected_sources:
        return "Error: No data sources are selected or configured for this conversation."

    # ── Cache resolved sources ─────────────────────────────────────
    if cache and not cache.get("sources"):
        cache["sources"] = selected_sources
        logger.debug("query_data_source: cached %d sources for thread %s", len(selected_sources), conversation_id)

    # ── Handle "查看数据源" / "schema overview" queries ────────────
    # If the query is about seeing what data sources are available
    # (rather than a specific data query), return the full snapshot.
    schema_query_patterns = re.compile(
        r"(数据源|有哪些|有什么|查看|结构|schema|表结构|所有表|表名|字段|"
        r"files?|documents?|pdf|连接|绑定|关联|当前)"
    )
    if schema_query_patterns.search(query) and not any(
        kw in query for kw in ("查询", "统计", "计算", "分析", "检索", "搜索", "count", "sum", "group")
    ):
        block = _build_schema_block(selected_sources)
        return (
            f"当前对话绑定了以下数据源：\n\n"
            f"{block}\n\n"
            f"如需生成报告，请调用 `generate_report(title=..., user_query=...)`。"
        )

    # ── Soft redirect for report-intent queries ────────────────────
    if _REPORT_INTENT_PATTERNS.search(query):
        block = _build_schema_block(selected_sources)
        return (
            f"检测到报告需求。当前数据源：\n\n"
            f"{block}\n\n"
            f"请调用 `generate_report(title=..., user_query=...)` 自动完成报告生成。"
        )

    # 2. Match target data source
    target_ds = None
    if datasource_id:
        for ds in selected_sources:
            if ds.get("datasource_id") == datasource_id:
                target_ds = ds
                break
        if not target_ds:
            return f"Error: Data source with ID '{datasource_id}' not found in active data sources."
    elif datasource_name:
        for ds in selected_sources:
            if ds.get("name", "").lower() == datasource_name.lower():
                target_ds = ds
                break
        if not target_ds:
            return f"Error: Data source with name '{datasource_name}' not found in active data sources."
    else:
        # Auto-detect: prioritize sql/es sources
        sql_es_sources = [ds for ds in selected_sources if ds.get("type") in ("sql", "es")]
        if len(sql_es_sources) == 1:
            target_ds = sql_es_sources[0]
        elif len(selected_sources) == 1:
            target_ds = selected_sources[0]
        elif not sql_es_sources:
            return f"Error: No SQL or Elasticsearch data sources found in active data sources: {[ds.get('name') for ds in selected_sources]}"
        else:
            return f"Error: Multiple SQL/Elasticsearch data sources found. Please specify which one to query using 'datasource_name' or 'datasource_id'. Available: {[ds.get('name') for ds in sql_es_sources]}"

    ds_type = target_ds.get("type")
    metadata = target_ds.get("metadata") or {}

    try:
        from app.gateway.services_v1.nl_query_engine import nl_query_engine
    except ImportError as e:
        logger.error("Failed to import nl_query_engine: %s", e)
        return "Error: Natural Language Query Engine is not available on this server."

    conversation_id = _get_thread_id(runtime)

    if ds_type == "sql":
        try:
            res = await nl_query_engine.query_sql(query, metadata)
            if "error" in res:
                return f"SQL Query Error: {res['error']}"

            columns = res.get("columns", [])
            rows = res.get("rows", [])
            row_count = res.get("row_count", 0)
            sql_stmt = res.get("generated_query", "")

            # Save full result to local sandbox workspace
            if conversation_id:
                full_res = {
                    "datasource_name": target_ds.get("name"),
                    "datasource_id": target_ds.get("datasource_id"),
                    "query": query,
                    "type": ds_type,
                    "generated_query": sql_stmt,
                    "columns": columns,
                    "rows": rows,
                    "row_count": row_count
                }
                _save_query_results(runtime, conversation_id, full_res)

            out = [
                f"Successfully queried database '{target_ds.get('name')}'",
                f"SQL Statement: {sql_stmt}",
                f"Returned {row_count} rows. The complete result set has been saved to the thread's local sandbox workspace as 'user-data/workspace/query_results.json'."
            ]
            if columns and rows:
                out.append("\nSample data (first 5 rows):")
                header = " | ".join(str(c) for c in columns)
                out.append(header)
                out.append("-" * len(header))
                for row in rows[:5]:
                    out.append(" | ".join(str(val) for val in row))
            else:
                out.append("(No columns returned)")
            return "\n".join(out)
        except Exception as e:
            logger.exception("SQL Query execution exception")
            return f"Error executing SQL query: {e}"

    elif ds_type == "es":
        try:
            res = await nl_query_engine.query_es(query, metadata)
            if "error" in res:
                return f"Elasticsearch Query Error: {res['error']}"

            columns = res.get("columns", [])
            rows = res.get("rows", [])
            row_count = res.get("row_count", 0)
            es_dsl = res.get("generated_query", "")

            # Save full result to local sandbox workspace
            if conversation_id:
                full_res = {
                    "datasource_name": target_ds.get("name"),
                    "datasource_id": target_ds.get("datasource_id"),
                    "query": query,
                    "type": ds_type,
                    "generated_query": es_dsl,
                    "columns": columns,
                    "rows": rows,
                    "row_count": row_count
                }
                _save_query_results(runtime, conversation_id, full_res)

            out = [
                f"Successfully queried Elasticsearch index '{target_ds.get('name')}'",
                f"ES Query DSL: {es_dsl}",
                f"Returned {row_count} rows. The complete result set has been saved to the thread's local sandbox workspace as 'user-data/workspace/query_results.json'."
            ]
            if columns and rows:
                out.append("\nSample data (first 5 rows):")
                header = " | ".join(str(c) for c in columns)
                out.append(header)
                out.append("-" * len(header))
                for row in rows[:5]:
                    out.append(" | ".join(str(val) for val in row))
            else:
                out.append("(No columns returned)")
            return "\n".join(out)
        except Exception as e:
            logger.exception("Elasticsearch Query execution exception")
            return f"Error executing Elasticsearch query: {e}"

    else:
        # Text, file, url
        content = target_ds.get("content") or ""
        return f"Data source '{target_ds.get('name')}' ({ds_type}) content:\n{content}"
