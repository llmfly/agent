"""Quick test: entity linking hint generation."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../backend'))
os.environ['DEER_FLOW_DISABLE_DB'] = '1'

from app.gateway.services_v1.text_to_sql.schema_linking import LinkedEntity
from app.gateway.services_v1.text_to_sql.schema_store import ColumnSchema, TableSchema

cols = [
    ColumnSchema(name='enroll_year', dtype='INT', nullable=True, is_primary_key=False, is_foreign_key=False, sample_values=[2024, 2023, 2022], comment='入学年份'),
    ColumnSchema(name='class_name', dtype='VARCHAR(30)', nullable=True, is_primary_key=False, is_foreign_key=False, sample_values=['计科2024-1班', '计科2024-2班'], comment='班级'),
    ColumnSchema(name='major', dtype='VARCHAR(50)', nullable=True, is_primary_key=False, is_foreign_key=False, sample_values=['计算机科学与技术', '软件工程'], comment='专业'),
]
t = TableSchema(name='students', columns=cols, row_count=35)

entities = [
    LinkedEntity(mention='2024', table='students', column='enroll_year', confidence=0.95, match_type='sample_value'),
    LinkedEntity(mention='专业', table='students', column='major', confidence=1.0, match_type='exact'),
]

positive = [e for e in entities if e.match_type not in ('comment',)]
parts = ['### 字段映射规则 (必须遵守):']
for e in positive:
    sample_hint = ''
    if t.name == e.table and e.column:
        for c in t.columns:
            if c.name == e.column and c.sample_values:
                svs = ', '.join(str(v)[:15] for v in c.sample_values[:3])
                sample_hint = f'  (字段示例值: {svs})'
                break
    parts.append(f'  - 用户问题中的"{e.mention}" -> 必须使用 `{e.table}`.`{e.column}`{sample_hint}')
parts.append('')

result = '\n'.join(parts)
print(result)
print()
assert 'enroll_year' in result
assert 'class_name' not in result
print('HINT GENERATION OK!')
