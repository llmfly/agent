import subprocess
import sys

# Check available PDF tools
for cmd in ["pdftotext", "pdfinfo", "pdftotext", "mutool"]:
    try:
        result = subprocess.run(["which", cmd], capture_output=True, text=True)
        if result.stdout.strip():
            print(f"Available: {cmd} at {result.stdout.strip()}")
    except:
        pass

# Try pdftotext
for pdf in ["/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/75b62093-6620-41ed-b3ce-70c2a69ad6ad/user-data/uploads/崔亚飞.pdf", "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/75b62093-6620-41ed-b3ce-70c2a69ad6ad/user-data/uploads/杨佳文-java后端-v8.pdf"]:
    print(f"\n{'='*60}")
    print(f"Processing: {pdf}")
    print('='*60)
    try:
        result = subprocess.run(["pdftotext", pdf, "-"], capture_output=True, text=True)
        if result.returncode == 0:
            print(result.stdout[:5000])
            if len(result.stdout) > 5000:
                print(f"... [truncated, total {len(result.stdout)} chars]")
        else:
            print(f"Error: {result.stderr}")
    except FileNotFoundError:
        print("pdftotext not available")
        break
