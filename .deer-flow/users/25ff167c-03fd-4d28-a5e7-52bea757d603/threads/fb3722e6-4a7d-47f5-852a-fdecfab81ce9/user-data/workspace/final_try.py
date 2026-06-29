import subprocess, sys
# Just run it as a subprocess with python3 -c
code = '''
import subprocess, sys
r = subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF", "-q"], capture_output=True, timeout=60)
import fitz, os
os.makedirs("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs", exist_ok=True)
for path, name in [("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/崔亚飞.pdf", "崔亚飞"), ("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/杨佳文-java后端-v8.pdf", "杨佳文")]:
    doc = fitz.open(path)
    text = "\\n".join(p.get_text() for p in doc if p.get_text().strip())
    doc.close()
    with open(f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/{name}.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print(f"=== {name} ===\\n{text[:2000]}\\n...")
print("OK")
'''
r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180,
                   env={**__import__('os').environ, 'PYTHONIOENCODING': 'utf-8'})
print("STDOUT:", r.stdout[:5000])
if r.stderr:
    print("STDERR:", r.stderr[:1000])
