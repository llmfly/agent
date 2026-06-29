"""Context Builder — assembles the LLM prompt from schema + question."""

from __future__ import annotations

from .few_shot_store import FewShotExample
from .schema_store import TableSchema

SYSTEM_PROMPT = """你是一个 SQL 生成助手。根据数据库表结构和用户问题，输出 SQL 查询。

## 规则
1. 只输出 SQL，不要有任何解释或其他文字
2. SQL 必须以 SELECT 开头
3. 列名用反引号包围
4. 用 JOIN 替代 IN (SELECT ...) 子查询
5. 添加 LIMIT 限制结果数量

## 输出格式
直接输出 SQL，不要用 Markdown 代码块包裹"""


class ContextBuilder:
    """Assembles prompt from fixed system prompt + schema + few-shot + question."""

    def build(
        self,
        question: str,
        *,
        tables: list[TableSchema] | None = None,
        few_shot: list[FewShotExample] | None = None,
        history: str | None = None,
        max_results: int = 50,
    ) -> list[dict[str, str]]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"LIMIT 最多 {max_results} 条"},
        ]

        # Schema context
        if tables:
            schema_parts = [f"可用表 ({len(tables)} 张):"]
            for t in tables:
                schema_parts.append("")
                schema_parts.append(t.ddl)
            messages.append({"role": "system", "content": "\n".join(schema_parts)})

        # Few-shot examples
        if few_shot:
            fs_parts = ["### 参考示例:"]
            for i, ex in enumerate(few_shot, 1):
                fs_parts.append(f"  [{i}] 问题: {ex.question}")
                fs_parts.append(f"      SQL: {ex.sql}")
            messages.append({"role": "user", "content": "\n".join(fs_parts)})
            messages.append({"role": "assistant", "content": "已理解。"})

        # History
        if history:
            messages.append({"role": "user", "content": f"### 历史:\n{history}"})
            messages.append({"role": "assistant", "content": "已理解。"})

        # Question
        messages.append({"role": "user", "content": f"### 问题:\n{question}\n\nSQL:"})
        return messages
