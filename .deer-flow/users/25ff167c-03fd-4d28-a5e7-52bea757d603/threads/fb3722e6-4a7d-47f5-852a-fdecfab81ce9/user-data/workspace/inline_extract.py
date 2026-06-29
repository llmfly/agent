import subprocess, sys, os

# Direct execution
try:
    r = subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF", "-q"], 
                       capture_output=True, text=True, timeout=60)
    print("Pip install:", r.returncode)
except Exception as e:
    print("Pip error:", e)

# Now run extraction inline
code = """
import fitz, os
out = '/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/resume_text.txt'
os.makedirs('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs', exist_ok=True)

with open(out, 'w', encoding='utf-8') as f:
    for path, name in [('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/崔亚飞.pdf', '崔亚飞'),
                        ('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/杨佳文-java后端-v8.pdf', '杨佳文')]:
        doc = fitz.open(path)
        f.write(f'\\n{\"=\"*80}\\n=== {name} ===\\n{\"=\"*80}\\n\\n')
        for page in doc:
            t = page.get_text()
            if t.strip():
                f.write(t + '\\n\\n')
        doc.close()
print('Done! Size:', os.path.getsize(out))
"""
exec(code)
