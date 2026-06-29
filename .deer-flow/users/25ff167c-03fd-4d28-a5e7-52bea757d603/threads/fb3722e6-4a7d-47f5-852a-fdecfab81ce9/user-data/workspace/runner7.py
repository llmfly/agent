import subprocess, sys, os

script_path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/workspace/_extract.py"

# write the script file with proper encoding
with open(script_path, "w", encoding="utf-8") as f:
    f.write('''import subprocess as sp, sys, os
sp.run([sys.executable, "-m", "pip", "install", "PyMuPDF", "-q"], capture_output=True, timeout=60)
import fitz
os.makedirs("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs", exist_ok=True)
for path, name in [("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/崔亚飞.pdf", "崔亚飞"), ("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/杨佳文-java后端-v8.pdf", "杨佳文")]:
    d = fitz.open(path)
    txt = "\\n".join(p.get_text() for p in d)
    d.close()
    with open(f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/{name}.txt", "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"=== {name} ({len(txt)} chars) ===")
    print(txt[:2000])
    if len(txt) > 2000:
        print("...[truncated]")
print("ALL DONE")
''')

env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'

r = subprocess.run([sys.executable, script_path], capture_output=True, text=True, timeout=180, env=env)
print("=== STDOUT ===")
print(r.stdout[:8000])
if r.stderr:
    print("\n=== STDERR (first 1000 chars) ===")
    print(r.stderr[:1000])
print(f"\nReturn code: {r.returncode}")
