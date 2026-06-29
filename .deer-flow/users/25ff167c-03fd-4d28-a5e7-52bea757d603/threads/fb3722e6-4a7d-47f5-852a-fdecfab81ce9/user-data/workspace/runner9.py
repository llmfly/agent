"""Use subprocess to install PyMuPDF and extract"""
import subprocess, sys, os

env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'

script_content = r'''
import subprocess as sp, sys
sp.run([sys.executable, "-m", "pip", "install", "PyMuPDF", "-q"], capture_output=True, timeout=60)
import fitz, os
os.makedirs("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs", exist_ok=True)
for path, name in [("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/崔亚飞.pdf", "崔亚飞"), ("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/杨佳文-java后端-v8.pdf", "杨佳文")]:
    d = fitz.open(path)
    all_pages = []
    for p in d:
        t = p.get_text()
        if t.strip():
            all_pages.append(t)
    d.close()
    full = "\n".join(all_pages)
    # Save to output
    with open(f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/{name}.txt", "w", encoding="utf-8") as f:
        f.write(full)
    print(f"=== {name} ({len(full)} chars) ===")
    print(full)
print("ALL DONE")
'''

with open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/workspace/exec_script.py", "w", encoding="utf-8") as f:
    f.write(script_content)

r = subprocess.run([sys.executable, "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/workspace/exec_script.py"], 
                  capture_output=True, text=True, timeout=180, env=env)
# Save output to a file
output_log = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/workspace/output_log.txt"
with open(output_log, "w", encoding="utf-8") as f:
    f.write("STDOUT:\n" + r.stdout)
    if r.stderr:
        f.write("\nSTDERR:\n" + r.stderr[:2000])
    f.write(f"\nRC: {r.returncode}")
print(f"Output saved to {output_log}")
print("STDOUT:", r.stdout[:5000])
if r.stderr:
    print("STDERR:", r.stderr[:500])
print("RC:", r.returncode)
