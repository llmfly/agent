"""Generate v1 OpenAPI spec and save to apipost directory."""
import os, json, sys

# Add backend directory to path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.insert(0, backend_dir)

os.environ['DEER_FLOW_DISABLE_DB'] = '1'

from app.gateway.app import create_app

app = create_app()
spec = app.openapi()

# Filter only v1 paths
v1_paths = {k: v for k, v in spec['paths'].items() if '/api/v1/' in k}

# Build clean v1-only OpenAPI spec
v1_spec = {
    'openapi': '3.0.3',
    'info': {
        'title': 'intelli-engine v1 External API',
        'version': '0.1.0',
        'description': (
            'AI Agent Backend Platform API\n\n'
            '提供数据源管理、自然语言查询（Text-to-SQL/ES）、报告生成等 AI 能力。\n\n'
            '## 核心流程\n'
            '1. 注册数据源 (text/file/url/sql/es)\n'
            '2. 自然语言查询数据源 → 自动生成 SQL/ES DSL 并执行\n'
            '3. 基于数据源生成报告 → 输出 DOCX/HTML\n'
            '4. 下载报告产物'
        ),
    },
    'servers': [
        {'url': 'http://localhost:8081', 'description': '本地开发'},
    ],
    'paths': v1_paths,
    'components': spec.get('components', {}),
    'tags': [t for t in spec.get('tags', []) if t['name'].startswith('v1-')],
}

output_dir = r'D:\code\agent\intelli-engine\apipost'
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, 'intelli-engine-v1-api.json')

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(v1_spec, f, ensure_ascii=False, indent=2)

print(f'Generated: {len(v1_paths)} v1 endpoints -> {output_path}')
for p in sorted(v1_paths.keys()):
    methods = list(v1_paths[p].keys())
    print(f'  {p} [{",".join(methods)}]')
