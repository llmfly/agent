import subprocess, sys, os

env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'

result = subprocess.run(
    [sys.executable, "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/workspace/run_now.py"],
    capture_output=True, text=True, timeout=180,
    env=env
)

# Write all output to a file for reading
out_log = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/workspace/exec_log.txt"
with open(out_log, "w", encoding="utf-8") as f:
    f.write("=== STDOUT ===\n")
    f.write(result.stdout)
    if result.stderr:
        f.write("\n=== STDERR ===\n")
        f.write(result.stderr[:1000])
    f.write(f"\n\nReturn code: {result.returncode}")
    
    # Also check output files
    for name in ["崔亚飞", "杨佳文"]:
        path = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/{name}.txt"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as rf:
                content = rf.read()
            f.write(f"\n\n{'='*60}")
            f.write(f"\n=== {name}.txt ({len(content)} chars) ===")
            f.write(f"\n{'='*60}\n")
            f.write(content)
        else:
            f.write(f"\n{name}.txt: NOT FOUND")

print(f"Execution log written to {out_log}")
