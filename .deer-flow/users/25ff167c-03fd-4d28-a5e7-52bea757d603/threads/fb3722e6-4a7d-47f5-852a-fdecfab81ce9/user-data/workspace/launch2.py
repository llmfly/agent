import subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
result = subprocess.run([sys.executable, "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/workspace/run_now.py"],
                       capture_output=True, text=True, timeout=180,
                       env={**__import__('os').environ, 'PYTHONIOENCODING': 'utf-8'})
print(result.stdout)
if result.stderr:
    print("=== STDERR ===")
    print(result.stderr[:1000])
