import subprocess, sys

# Step 1: install PyMuPDF
install = subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF", "-q"], 
                        capture_output=True, text=True, timeout=60)
print("Install:", install.returncode)

# Step 2: ensure we're in right context
# Just import and test
code = """
import fitz, os
os.makedirs('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs', exist_ok=True)
results = {}
for path, name in [('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/崔亚飞.pdf', '崔亚飞'),
                    ('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/杨佳文-java后端-v8.pdf', '杨佳文')]:
    doc = fitz.open(path)
    text = '\\n'.join(p.get_text() for p in doc)
    results[name] = text
    doc.close()
    with open(f'/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/{name}.txt', 'w', encoding='utf-8') as f:
        f.write(text)
for k, v in results.items():
    print(f'{k}: {len(v)} chars')
    print(v[:1000])
    print('---')
"""

result = subprocess.run([sys.executable, "-c", code], 
                       capture_output=True, text=True, timeout=180)
print("Result:", result.returncode)
print("STDOUT:", result.stdout[:5000])
if result.stderr:
    print("STDERR:", result.stderr[:1000])
