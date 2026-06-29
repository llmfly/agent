"""NL Query Engine — minimal Text-to-SQL pipeline.

Pipeline:
  1. SchemaRetriever (auto-discover + vector Top-K)
  2. ContextBuilder (assemble prompt)
  3. LLM → SQL generation
  4. SQLGlotValidator (lightweight AST check)
  5. Execute + error retry + empty result retry
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import quote

from langchain_core.messages import HumanMessage, SystemMessage

from .text_to_sql.context_builder import ContextBuilder
from .text_to_sql.few_shot_store import FewShotStore
from .text_to_sql.schema_store import SchemaStore
from .text_to_sql.sql_glot_validator import SQLGlotValidator

logger = logging.getLogger(__name__)

MAX_RETRIES = 1  # 2 total attempts: initial + 1 retry. Column-name errors won't fix themselves with more retries.


def _build_sqlalchemy_url(metadata: dict[str, Any]) -> str:
    db_type = metadata.get("db_type", "mysql")
    user = quote(metadata.get("username", ""), safe="")
    password = quote(metadata.get("password", ""), safe="")
    host = metadata.get("host", "localhost")
    port = metadata.get("port", 3306)
    database = metadata.get("database", "")
    if db_type == "mysql":
        return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"
    elif db_type == "postgresql":
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    elif db_type == "sqlite":
        return f"sqlite+aiosqlite:///{database}"
    elif db_type == "mssql":
        return f"mssql+aioodbc://{user}:{password}@{host}:{port}/{database}?driver=ODBC+Driver+18+for+SQL+Server"
    elif db_type == "oracle":
        return f"oracle+oracledb://{user}:{password}@{host}:{port}/{database}"
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


# ---------------------------------------------------------------------------
# Schema auto-discovery
# ---------------------------------------------------------------------------


async def _discover_mysql_schema(metadata: dict[str, Any]) -> str:
    """Connect to MySQL and auto-discover all table schemas.

    Returns a formatted string describing all tables and columns,
    e.g.:
        Table: students
          - student_id VARCHAR(20) PK  -- 学号
          - name VARCHAR(50)  -- 姓名
          - gender ENUM('男','女')  -- 性别
    """
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
            # Step 1: Get all tables
            cursor.execute("SHOW TABLES")
            all_tables = [row[0] for row in cursor.fetchall()]

            # Filter by selected tables in metadata if specified
            user_tables = metadata.get("tables")
            if user_tables and isinstance(user_tables, list):
                tables = [t for t in all_tables if t in user_tables]
            else:
                tables = all_tables

            if not tables:
                return "（数据库中没有找到任何表或被过滤空了）"

            # Step 2: Collect per-table info
            table_columns: dict[str, list[tuple]] = {}
            table_fks: dict[str, dict[str, tuple[str, str]]] = {}
            table_row_counts: dict[str, int] = {}

            for table_name in tables:
                cursor.execute(f"SHOW FULL COLUMNS FROM `{table_name}`")
                table_columns[table_name] = cursor.fetchall()

                # FK info
                try:
                    cursor.execute(
                        "SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
                        "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
                        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND REFERENCED_TABLE_NAME IS NOT NULL",
                        (metadata.get("database", ""), table_name),
                    )
                    fk_rows = cursor.fetchall()
                    fk_map: dict[str, tuple[str, str]] = {}
                    for fk in fk_rows:
                        fk_map[fk[0]] = (fk[1], fk[2])
                    table_fks[table_name] = fk_map
                except Exception:
                    table_fks[table_name] = {}

                # Row count
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
                    table_row_counts[table_name] = cursor.fetchone()[0]
                except Exception:
                    table_row_counts[table_name] = 0

            # Step 3: Build schema description per table
            schema_parts = []
            for table_name in tables:
                columns = table_columns[table_name]
                fk_map = table_fks[table_name]

                schema_parts.append(f"### 表: {table_name}  (行数: {table_row_counts[table_name]})")
                for col in columns:
                    field_name = col[0]
                    col_type = col[1]
                    nullable_mark = "NULL" if col[3] == "YES" else "NOT NULL"
                    key_type = ""
                    if col[4] == "PRI":
                        key_type = " [PK]"
                    elif field_name in fk_map:
                        key_type = " [FK]"
                    elif col[4] == "MUL":
                        key_type = " [有索引]"
                    default_val = f" default={col[5]}" if col[5] is not None else ""
                    comment = col[8] if col[8] else ""

                    col_desc = f"  - {field_name} ({col_type}, {nullable_mark}){key_type}{default_val}"
                    if comment:
                        col_desc += f"  -- {comment}"
                    if field_name in fk_map:
                        ref_table, ref_col = fk_map[field_name]
                        col_desc += f"  → 关联 {ref_table}.{ref_col}"
                    schema_parts.append(col_desc)
                schema_parts.append("")

            # Step 4: Build relationship paths
            schema_parts.append("### 表关联路径 (JOIN 指南):")
            # Build reverse FK map: for each table, list which tables reference it
            reverse_fk: list[str] = []
            for tname in tables:
                for col_name, (ref_table, ref_col) in table_fks.get(tname, {}).items():
                    path = f"  {tname}.{col_name} → {ref_table}.{ref_col}  (通过 {col_name} 关联到 {ref_table} 表)"
                    reverse_fk.append(path)
            if reverse_fk:
                schema_parts.extend(reverse_fk)
            else:
                schema_parts.append("  (无外键关联)")

            schema_parts.append("")

            # Step 5: Build common query paths (heuristic)
            schema_parts.append("### 常见查询路径示例:")
            # Detect common patterns
            if "students" in tables and "enrollments" in tables and "courses" in tables:
                schema_parts.append(
                    "  学生-课程-成绩: students.student_id → enrollments.student_id → "
                    "enrollments.course_id → courses.course_id"
                )
            if "courses" in tables and "teachers" in tables:
                schema_parts.append(
                    "  课程-教师: courses.teacher_id → teachers.teacher_id"
                )
            if "students" in tables and "enrollments" in tables:
                schema_parts.append(
                    "  学生-选课: students.student_id → enrollments.student_id"
                )
            schema_parts.append("")

        result = "\n".join(schema_parts)
        return result

    finally:
        conn.close()
async def _discover_es_mapping(metadata: dict[str, Any]) -> str:
    """Connect to Elasticsearch and discover the index mapping fields."""
    from elasticsearch import AsyncElasticsearch

    hosts = metadata.get("hosts", ["http://localhost:9200"])
    index = metadata.get("index", "_all")
    auth = {}
    if metadata.get("username"):
        auth["basic_auth"] = (metadata["username"], metadata.get("password", ""))

    client = AsyncElasticsearch(hosts=hosts, **auth)
    try:
        mapping_data = await client.indices.get_mapping(index=index)
        
        # Parse mapping into a structured field list
        def parse_properties(properties: dict, prefix: str = "") -> list[str]:
            fields = []
            for name, info in properties.items():
                full_name = f"{prefix}{name}"
                field_type = info.get("type", "object")
                if "properties" in info:
                    fields.append(f"  - {full_name} (object)")
                    fields.extend(parse_properties(info["properties"], f"{full_name}."))
                else:
                    fields.append(f"  - {full_name} ({field_type})")
            return fields

        output_parts = []
        # Elasticsearch 8.x client returns mapping_data.body or mapping_data depending on compatibility,
        # but AsyncElasticsearch client typically returns a dict (or ObjectApiResponse which behaves like a dict)
        data_dict = mapping_data.body if hasattr(mapping_data, "body") else mapping_data
        if not isinstance(data_dict, dict) and hasattr(data_dict, "meta"):
            # Fallback
            data_dict = dict(data_dict)

        for idx, details in data_dict.items():
            properties = details.get("mappings", {}).get("properties", {})
            if properties:
                output_parts.append(f"### Index: {idx}")
                output_parts.extend(parse_properties(properties))
                output_parts.append("")
        
        if output_parts:
            return "\n".join(output_parts)
        return "（未找到任何字段映射信息）"
    except Exception as e:
        logger.warning("Failed to auto-discover ES mapping: %s", e)
        return "（无法自动获取索引映射信息）"
    finally:
        await client.close()


async def _discover_schema(metadata: dict[str, Any]) -> str:
    """Auto-discover database schema based on db_type.

    Falls back to user-provided table_schema if discovery fails or
    the database type is not supported.
    """
    db_type = metadata.get("db_type", "mysql")
    user_schema = metadata.get("table_schema", "")

    if db_type == "mysql":
        try:
            logger.info("Auto-discovering MySQL schema for %s", metadata.get("database", ""))
            schema = await _discover_mysql_schema(metadata)
            logger.info("Schema discovery complete: %d characters", len(schema))
            return schema
        except ImportError as e:
            logger.warning("Missing driver for schema discovery: %s", e)
        except Exception as e:
            logger.warning("Schema auto-discovery failed: %s. Falling back to user-provided schema.", e)

    # Fallback
    if user_schema:
        logger.info("Using user-provided table schema")
        return user_schema

    return "（无法获取数据库表结构信息）"


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

TEXT_TO_SQL_SYSTEM_PROMPT = """你是一个专业的 Text-to-SQL 助手。根据数据库表结构和用户问题生成 SQL 查询。

## 数据库信息
- 数据库类型: {db_type}
- 数据库名: {database}

## 完整表结构（含字段类型、注释、关联关系）
{table_schema}

## 核心规则
1. 只输出 SQL 查询语句，不要有任何解释或其他文字
2. SQL 必须以 SELECT 开头，禁止 DELETE/UPDATE/INSERT/DROP/ALTER/CREATE/TRUNCATE
3. 列名用反引号 ` 包围
4. 使用 LIMIT 限制结果数量（最多 {max_results} 条）

## 表关联规则（重要！）
1. 优先使用 JOIN 进行表关联，不要使用 IN (SELECT ...) 子查询
2. 表关联必须使用 "### 表关联路径" 中标注的外键关系
3. 如果查询需要跨多张表，按照 "常见查询路径示例" 中的路径进行 JOIN
4. 例如查询"学生的课程成绩"需要 JOIN: students → enrollments → courses
5. 例如查询"某课程的授课教师"需要 JOIN: courses → teachers

## 输出格式
直接输出 SQL，不要用 Markdown 代码块包裹
"""

TEXT_TO_SQL_ANALYSIS_PROMPT = """根据用户的自然语言查询，分析并生成 SQL 查询语句。

用户查询: {user_query}

请输出 SQL:"""

# Phase 1 prompt: let LLM identify which tables are relevant before seeing any column details.
# Much more accurate than embedding-only retrieval for Chinese + English mixed schemas.
TABLE_LINKING_PROMPT = """你是一个数据库专家。根据用户的问题，从以下数据库表中选择最相关的 1-3 张表。

数据库类型: {db_type}
数据库名: {database}

可用表列表:
{table_list}

规则:
1. 只输出表名，每行一个，不要有其他文字
2. 选择与用户问题最相关的表
3. 如果问题涉及聚合/统计，优先选行数多的明细表
4. 如果多张表可以通过外键关联，一起输出

用户问题: {user_query}

请输出最相关的表名（每行一个）:"""

TEXT_TO_ES_SYSTEM_PROMPT = """你是一个专业的 Text-to-Elasticsearch 助手。你的任务是将用户的自然语言问题转换为 Elasticsearch 查询 DSL。

## ES 索引信息
- 索引名: {index}
- 索引映射/字段信息:
{index_mapping}

## 规则
1. 只输出 Elasticsearch 查询 DSL JSON，不要包含任何解释或其他文字
2. 查询必须使用 `{{"query": {{...}}}}` 格式
3. 不要使用 `delete`, `update`, `_bulk` 等修改性操作
4. 使用 `size` 限制结果数量（最多 {max_results} 条）
5. 输出格式：直接输出 JSON，不要用 Markdown 代码块包裹
6. 需要返回的字段用 `_source` 指定
"""

TEXT_TO_ES_ANALYSIS_PROMPT = """根据用户的自然语言查询，分析并生成 Elasticsearch 查询 DSL。

用户查询: {user_query}

请输出 ES 查询 JSON:"""


# ---------------------------------------------------------------------------
# Query execution helpers
# ---------------------------------------------------------------------------


async def _execute_sql(sql: str, metadata: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    from sqlalchemy import text as sql_text
    from sqlalchemy.ext.asyncio import create_async_engine
    url = _build_sqlalchemy_url(metadata)
    engine = create_async_engine(url, echo=False)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(sql_text(sql))
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchall()]
            return columns, rows
    finally:
        await engine.dispose()


async def _execute_es(es_query: dict, metadata: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    from elasticsearch import AsyncElasticsearch
    hosts = metadata.get("hosts", ["http://localhost:9200"])
    index = metadata.get("index", "_all")
    auth = {}
    if metadata.get("username"):
        auth["basic_auth"] = (metadata["username"], metadata.get("password", ""))
    client = AsyncElasticsearch(hosts=hosts, **auth)
    try:
        if isinstance(es_query, str):
            es_query = json.loads(es_query)
        es_size = es_query.pop("size", 50)
        response = await client.search(index=index, body=es_query, size=es_size)

        hits = response.get("hits", {}).get("hits", [])
        if not hits:
            return ["_id"], []
        columns = set()
        for hit in hits:
            src = hit.get("_source", {})
            columns.update(src.keys())
        columns = sorted(columns)
        if "_id" not in columns:
            columns.insert(0, "_id")
        rows = []
        for hit in hits:
            src = hit.get("_source", {})
            row = [hit.get("_id", "")]
            for col in columns[1:]:
                row.append(src.get(col, ""))
            rows.append(row)
        return columns, rows
    finally:
        await client.close()


def _clean_sql(raw: str) -> str:
    raw = re.sub(r"^```(?:sql)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


class NLQueryEngine:
    """Minimal Text-to-SQL engine — 4-step pipeline with error retry."""

    def __init__(self) -> None:
        self._llm = None
        self._schema_stores: dict[str, SchemaStore] = {}
        self._few_shot_store = FewShotStore()
        self._validator = SQLGlotValidator()
        self._context_builder = ContextBuilder()

    async def _ensure_llm(self) -> Any:
        if self._llm is None:
            from deerflow.config.app_config import get_app_config
            from deerflow.models.factory import create_chat_model
            app_config = get_app_config()
            if not app_config.models:
                raise ValueError("No models configured.")
            self._llm = create_chat_model(app_config.models[0].name, app_config=app_config)
        return self._llm

    async def _ensure_schema(self, metadata: dict[str, Any]) -> SchemaStore:
        db_type = metadata.get("db_type", "mysql")
        host = metadata.get("host", "localhost")
        port = metadata.get("port", 3306)
        database = metadata.get("database", "")
        db_key = f"{db_type}://{host}:{port}/{database}"

        if db_key not in self._schema_stores:
            store = SchemaStore()
            if db_type == "mysql":
                await store.load_from_mysql(metadata)
            self._schema_stores[db_key] = store
            logger.info("Schema loaded for %s: %d tables", db_key, store.total_tables)
        return self._schema_stores[db_key]

    async def query_sql(self, user_query: str, metadata: dict[str, Any], max_results: int = 50) -> dict[str, Any]:
        schema = await self._ensure_schema(metadata)
        db_type = metadata.get("db_type", "mysql")

        # ═══════════════════════════════════════════════════════════════
        # Phase 1: Table Linking — LLM picks relevant tables by name only
        # ═══════════════════════════════════════════════════════════════
        # Build a compact table list: name + row count + first few columns
        table_lines = []
        for t in schema.all_tables:
            col_preview = ", ".join(
                f"{c.name}" + (f"({c.comment})" if c.comment else "")
                for c in t.columns[:6]
            )
            table_lines.append(f"  - {t.name} (行数: ~{t.row_count}, 字段: {col_preview})")
        table_list_str = "\n".join(table_lines)

        llm = await self._ensure_llm()
        linking_messages = [
            SystemMessage(content=TABLE_LINKING_PROMPT.format(
                db_type=db_type,
                database=metadata.get("database", ""),
                table_list=table_list_str,
                user_query=user_query,
            )),
        ]
        linking_resp = await llm.ainvoke(linking_messages)
        raw_linked = (linking_resp.content if hasattr(linking_resp, "content") else str(linking_resp)).strip()
        # Parse table names from LLM output (one per line)
        linked_names = []
        for line in raw_linked.splitlines():
            line = line.strip().strip("-*`").strip()
            if line and schema.get_table(line):
                linked_names.append(line)

        if not linked_names:
            logger.warning("Table linking returned no valid tables; falling back to embedding retrieval")
            linked_tables = await schema.retrieve(user_query, top_k=min(5, schema.total_tables))
        else:
            linked_tables = [schema.get_table(n) for n in linked_names if schema.get_table(n)]
            logger.info("Phase 1 (table linking): %s -> %s", user_query[:50], [t.name for t in linked_tables])

        # ═══════════════════════════════════════════════════════════════
        # Phase 2: SQL Generation — full DDL for selected tables only
        # ═══════════════════════════════════════════════════════════════
        few_shots = await self._few_shot_store.retrieve(user_query, top_k=3)
        messages = self._context_builder.build(
            user_query, tables=linked_tables, few_shot=few_shots, max_results=max_results,
        )

        sql = ""
        last_error = ""

        for attempt in range(MAX_RETRIES + 1):
            if attempt == 0:
                response = await llm.ainvoke([
                    SystemMessage(content=m["content"]) if m["role"] == "system"
                    else HumanMessage(content=m["content"])
                    for m in messages
                ])
                sql = _clean_sql(response.content if hasattr(response, "content") else str(response))
            else:
                # Error retry: add error feedback to the prompt, including valid column
                # names so the LLM stops guessing hallucinated columns.
                valid_columns = []
                if schema:
                    for t in linked_tables:
                        for c in t.columns:
                            valid_columns.append(f"{t.name}.{c.name}({c.dtype})")
                col_hint = ""
                if valid_columns:
                    col_hint = "\n当前表的有效列名:\n" + "\n".join(f"  - {c}" for c in valid_columns[:40])
                retry_prompt = (
                    f"你之前生成的 SQL 存在问题，请修正。\n\n"
                    f"原始问题: {user_query}\n"
                    f"之前的 SQL: {sql}\n"
                    f"错误: {last_error}{col_hint}\n\n"
                    f"请输出修正后的 SQL (只使用上面列出的有效列名):"
                )
                response = await llm.ainvoke([
                    SystemMessage(content=m["content"])
                    for m in messages if m["role"] == "system"
                ] + [
                    HumanMessage(content=retry_prompt),
                ])
                sql = _clean_sql(response.content if hasattr(response, "content") else str(response))

            logger.info("SQL attempt %d: %s", attempt + 1, sql[:80])

            # Validate
            vr = self._validator.validate(sql, dialect=db_type)
            if not vr.is_valid:
                last_error = "; ".join(vr.errors)
                logger.warning("Validation failed: %s", last_error)
                continue

            # Execute
            try:
                columns, rows = await _execute_sql(sql, metadata)

                # 5. Empty result retry
                if len(rows) == 0:
                    last_error = "SQL 执行结果为空，可能查询条件不正确"
                    logger.warning("Empty result (attempt %d), retrying...", attempt + 1)
                    sql = f"{sql}  -- [返回0行]"
                    if attempt < MAX_RETRIES:
                        continue

                logger.info("SQL success: %d rows", len(rows))
                return {
                    "generated_query": sql, "columns": columns, "rows": rows,
                    "row_count": len(rows),
                }
            except Exception as e:
                last_error = str(e)
                logger.warning("SQL execution failed: %s", last_error)
                continue

        return {
            "generated_query": sql, "columns": [], "rows": [],
            "row_count": 0, "error": last_error or "SQL generation failed",
        }

    async def query_es(self, user_query: str, metadata: dict[str, Any], max_results: int = 50) -> dict[str, Any]:
        index = metadata.get("index", "_all")
        index_mapping = metadata.get("index_mapping", "")
        if not index_mapping or index_mapping == "（未提供索引映射信息）":
            logger.info("Auto-discovering ES mappings for index: %s", index)
            index_mapping = await _discover_es_mapping(metadata)
            logger.info("Discovered ES mapping:\n%s", index_mapping[:500])

        prompt = f"""You are an Elasticsearch Query DSL generator.

Index: {index}
Mapping: {index_mapping}

Rules:
1. Output valid ES Query DSL JSON, for example: {{"query":{{...}}, "_source": [...], "size": N}}
2. The size value must not exceed {max_results}.
3. Output JSON only, without Markdown code fences.

User query: {user_query}
ES DSL:"""

        llm = await self._ensure_llm()
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = _clean_sql(response.content if hasattr(response, "content") else str(response))

        try:
            es_query = json.loads(content)
            columns, rows = await _execute_es(es_query, metadata)
            return {"generated_query": content, "columns": columns, "rows": rows, "row_count": len(rows)}
        except json.JSONDecodeError as e:
            return {"generated_query": content, "columns": [], "rows": [], "row_count": 0, "error": f"Invalid JSON: {e}"}
        except Exception as e:
            return {"generated_query": content, "columns": [], "rows": [], "row_count": 0, "error": str(e)}


nl_query_engine = NLQueryEngine()
