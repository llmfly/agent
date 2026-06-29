import json
import logging
import re
from pathlib import Path

from langchain.tools import tool

from deerflow.tools.types import Runtime

logger = logging.getLogger(__name__)

# ── Report-intent detection ─────────────────────────────────────────────
# If the user's query looks like they want a report or to understand
# the data structure, redirect them to generate_report instead.
_REPORT_INTENT_PATTERNS = re.compile(
    r"(报告|报表|生成.*报告|写.*报告|出.*报告|分析.*报告"
    r"|表结构|数据库结构|有哪些表|有什么表|schema|表名|字段名"
    r"|列名|所有表|数据字典|数据目录|元数据|表信息)"
)

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
    # 1. Resolve selected data sources
    # Priority: runtime context → runtime config → memory cache (v1 API registered)
    selected_sources = None
    if runtime.context:
        selected_sources = runtime.context.get("selected_data_sources")
    if not selected_sources:
        selected_sources = runtime.config.get("configurable", {}).get("selected_data_sources")
    if not selected_sources:
        selected_sources = runtime.config.get("context", {}).get("selected_data_sources")

    # Fallback: try reading from workspace data source service
    # (covers case where data source was registered via workspace API)
    if not selected_sources:
        try:
            conversation_id = _get_thread_id(runtime)
            if conversation_id:
                from app.gateway.services_v1.workspace_datasource_service import workspace_datasource_service

                selected_sources = await workspace_datasource_service.get_data_sources_for_conversation(conversation_id)

                # Fallback: old v1 memory cache (DataAsset not yet attached)
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
            pass  # Not running in app context
        except Exception as e:
            logger.warning("query_data_source: fallback lookup failed: %s", e)

    if not selected_sources:
        return "Error: No data sources are selected or configured for this conversation."

    # ── Report-intent guard ────────────────────────────────────────
    # If the query looks like "give me a report" or "show me the table
    # structure", refuse and direct to generate_report. This tool is
    # for ad-hoc data exploration, not report generation.
    if _REPORT_INTENT_PATTERNS.search(query):
        schema_summaries = []
        for ds in selected_sources:
            ss = ds.get("schema_summary") or {}
            name = ds.get("name", "?")
            ds_type = ds.get("type", "?")
            tables = ss.get("tables", [])
            if tables:
                summary_parts = [f"📦 {name} ({ds_type})"]
                for t in tables[:5]:
                    cols = ", ".join(
                        f"{c['name']}({c['type']})"
                        for c in t.get("columns", [])[:6]
                    )
                    summary_parts.append(f"  - {t['name']} : {cols}")
                schema_summaries.append("\n".join(summary_parts))

        if schema_summaries:
            schema_block = "\n".join(schema_summaries)
        else:
            # No schema_summary available yet — fall back to basic info
            schema_block = "\n".join(
                f"  {ds.get('name', '?')} ({ds.get('type', '?')})"
                for ds in selected_sources
            )

        return (
            f"⚠️ **请使用 `generate_report` 工具生成报告**\n\n"
            f"已了解的数据源结构：\n{schema_block}\n\n"
            f"直接调用 `generate_report(title=..., user_query=...)` 即可自动完成"
            f"数据查询→分析→报告渲染全流程，无需手动查询数据。"
            f"\n\n(query_data_source 返回了以上数据源信息，但查询内容 '{query[:80]}' 看起来像是报告需求，"
            f"请切换到 generate_report。如确实需要查询原始数据，请使用具体的数据查询语句。)"
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
