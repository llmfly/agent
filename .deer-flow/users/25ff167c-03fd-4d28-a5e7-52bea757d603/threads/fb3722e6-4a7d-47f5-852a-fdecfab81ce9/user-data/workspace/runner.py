import subprocess, sys, os

# Run the extraction script
result = subprocess.run(
    [sys.executable, "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/workspace/extract_pdfs.py"],
    capture_output=True, text=True, timeout=120
)
print("STDOUT:", result.stdout[-2000:])
print("STDERR:", result.stderr[-2000:])
print("RC:", result.returncode)

# Check if output file was created
out_path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/resume_text.txt"
if os.path.exists(out_path):
    with open(out_path, "r", encoding="utf-8") as f:
        content = f.read()
    print(f"\n=== OUTPUT FILE CONTENT ({len(content)} chars) ===")
    print(content[:5000])
    print("\n... (truncated)")
else:
    print("Output file not found")
    # Check workspace
    ws_path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/workspace/resume_text.txt"
    if os.path.exists(ws_path):
        with open(ws_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"\n=== WORKSPACE FILE CONTENT ({len(content)} chars) ===")
        print(content[:5000])
