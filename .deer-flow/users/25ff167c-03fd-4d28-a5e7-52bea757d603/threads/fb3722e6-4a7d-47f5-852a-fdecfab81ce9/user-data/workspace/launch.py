import subprocess, sys
r = subprocess.run([sys.executable, "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/workspace/go.py"], capture_output=True, text=True, timeout=120)
print(r.stdout)
if r.stderr:
    print("STDERR:", r.stderr[:500])
