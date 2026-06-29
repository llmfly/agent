import subprocess, sys

# Try pdftotext directly
try:
    r = subprocess.run(["pdftotext", "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/8867365d-0dd3-41cc-9b98-86d973e9da25/user-data/uploads/崔亚飞.pdf", "-"], capture_output=True, text=True, timeout=30)
    print("=== 崔亚飞.pdf ===")
    print(r.stdout[:4000])
    print(f"\n... (truncated, total: {len(r.stdout)} chars)")
    if r.stderr:
        print("STDERR:", r.stderr[:500])
except Exception as e:
    print(f"Error: {e}")

try:
    r = subprocess.run(["pdftotext", "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/8867365d-0dd3-41cc-9b98-86d973e9da25/user-data/uploads/杨佳文-java后端-v8.pdf", "-"], capture_output=True, text=True, timeout=30)
    print("\n=== 杨佳文-java后端-v8.pdf ===")
    print(r.stdout[:4000])
    print(f"\n... (truncated, total: {len(r.stdout)} chars)")
    if r.stderr:
        print("STDERR:", r.stderr[:500])
except Exception as e:
    print(f"Error: {e}")
