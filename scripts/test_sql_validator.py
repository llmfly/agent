"""Quick test for SQLGlot validator."""
import os, sys
os.environ['DEER_FLOW_DISABLE_DB'] = '1'

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../backend'))
from app.gateway.services_v1.text_to_sql.sql_glot_validator import SQLGlotValidator

v = SQLGlotValidator()

tests = [
    ('SELECT students.*, department AS prof FROM students GROUP BY department', False, 'star+group'),
    ('SELECT * FROM students GROUP BY major', False, 'star+group'),
    ('DELETE FROM students', False, 'delete'),
    ('SELECT s.*, c.name FROM students s GROUP BY s.student_id', False, 'star+group'),
    ('SELECT name, COUNT(*) FROM students GROUP BY name', True, 'valid agg'),
    ('SELECT DISTINCT major FROM students LIMIT 10', True, 'valid distinct'),
    ('SELECT major, COUNT(*) as cnt FROM students WHERE enroll_year = 2024 GROUP BY major', True, 'valid group+agg'),
    ('SELECT s.name, c.name, e.score FROM students s JOIN enrollments e JOIN courses c', True, 'valid join'),
]

all_ok = True
for sql, should_pass, label in tests:
    r = v.validate(sql)
    ok = r.is_valid == should_pass
    if not ok:
        all_ok = False
    status = 'PASS' if r.is_valid else ('REJECT:' + r.errors[0][:30] if r.errors else 'REJECT')
    mark = 'OK' if ok else 'FAIL'
    print(f'{mark:4s} {status:40s} {label}')

print()
print('ALL OK!' if all_ok else 'SOME FAILED!')
