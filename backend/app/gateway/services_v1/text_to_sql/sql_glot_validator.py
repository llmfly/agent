"""SQL validator — lightweight AST checks using sqlglot."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    import sqlglot
    from sqlglot.errors import ParseError
    SQLGLOT_AVAILABLE = True
except ImportError:
    SQLGLOT_AVAILABLE = False


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class SQLGlotValidator:
    """Lightweight SQL validator. Only catches clear errors."""

    def validate(self, sql: str, dialect: str = "mysql") -> ValidationResult:
        result = ValidationResult(is_valid=True)

        # 1. Basic checks
        stripped = sql.strip().upper()
        if not stripped.startswith("SELECT"):
            result.errors.append("SQL 必须以 SELECT 开头")
            result.is_valid = False
            return result

        if any(kw in stripped for kw in [" DELETE ", " DROP ", " ALTER ", " CREATE ", " TRUNCATE ", " INSERT "]):
            result.errors.append("只允许 SELECT 查询")
            result.is_valid = False
            return result

        # 2. SELECT * + GROUP BY (clear semantic error)
        if re.search(
            r"SELECT\s+(?:(?!COUNT|SUM|AVG|MAX|MIN).)*?\*(?:(?!FROM).)*?FROM.*GROUP\s+BY",
            sql, re.IGNORECASE | re.DOTALL,
        ):
            result.errors.append("GROUP BY 不能与 SELECT * 一起使用")
            result.is_valid = False
            return result

        # 3. GROUP BY no aggregate
        if re.search(r"GROUP\s+BY", sql, re.IGNORECASE) and not re.search(
            r"\b(?:COUNT|SUM|AVG|MAX|MIN|GROUP_CONCAT)\s*\(", sql, re.IGNORECASE,
        ):
            result.errors.append("GROUP BY 需要搭配聚合函数")
            result.is_valid = False
            return result

        # 4. AST parse (if available)
        if SQLGLOT_AVAILABLE:
            try:
                parsed = sqlglot.parse_one(sql, dialect=dialect)
                if not isinstance(parsed, sqlglot.exp.Select):
                    result.errors.append("语法错误：不是合法的 SELECT 语句")
                    result.is_valid = False
                    return result
            except ParseError as e:
                result.errors.append(f"SQL 语法错误: {e}")
                result.is_valid = False
                return result

        return result
