import subprocess, sys, os

env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'

# Write a small extraction script
script = """
import subprocess as sp, sys
sp.run([sys.executable, '-m', 'pip', 'install', 'PyMuPDF', '-q'], capture_output=True, timeout=60)
import fitz, os
os.makedirs('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs', exist_ok=True)
for path, name in [('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/崔亚飞.pdf', '崔亚飞'), ('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/杨佳文-java后端-v8.pdf', '杨佳文')]:
    d = fitz.open(path)
    txt = '\\n'.join(p.get_text() for p in d)
    d.close()
    with open(f'/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/{name}.txt', 'w', encoding='utf-8') as f:
        f.write(txt)
    print(f'=== {name} ({len(txt)} chars) ===')
    # Print ALL text
    print(txt)
print('ALL DONE')
"""

s = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=180, env=env)
print("STDOUT:", s.stdout[:10000])
if s.stderr:
    print("STDERR:", s.stderr[:2000])
print("RC:", s.returncode)
