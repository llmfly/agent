"""Text-to-SQL pipeline — minimal, generic, effective.

Architecture:
  User → SchemaRetriever → ContextBuilder → LLM → Executor → (error retry) → Result

Only 4 core modules:
- schema_store: Schema discovery + vector retrieval
- context_builder: Dynamic prompt assembly
- sql_glot_validator: AST syntax guard
- few_shot_store: Pure SQL pattern examples
"""

from .schema_store import SchemaStore, TableSchema, ColumnSchema
from .few_shot_store import FewShotStore, FewShotExample
from .context_builder import ContextBuilder
from .sql_glot_validator import SQLGlotValidator, ValidationResult

__all__ = [
    "SchemaStore", "TableSchema", "ColumnSchema",
    "FewShotStore", "FewShotExample",
    "ContextBuilder",
    "SQLGlotValidator", "ValidationResult",
]
