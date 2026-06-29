import subprocess, sys, os

# Set up environment
env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'

# Run the extraction script
result = subprocess.run(
    [sys.executable, "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/workspace/run_now.py"],
    capture_output=True, text=True, timeout=180,
    env=env
)

print("=== STDOUT ===")
print(result.stdout)

if result.stderr:
    print("\n=== STDERR ===")
    print(result.stderr[:1000])

print(f"\nReturn code: {result.returncode}")

# Now read the extracted files
for name in ["崔亚飞", "杨佳文"]:
    path = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/{name}.txt"
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"\n{name}.txt: {size} bytes")
    else:
        print(f"\n{name}.txt: NOT FOUND")
