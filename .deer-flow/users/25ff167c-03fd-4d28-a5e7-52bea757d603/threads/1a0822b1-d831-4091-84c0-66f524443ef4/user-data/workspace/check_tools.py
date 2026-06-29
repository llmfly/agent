#!/usr/bin/env python3
import subprocess, os

# Try to run pdftotext
for cmd in ["pdftotext", "mutool"]:
    r = subprocess.run(["which", cmd], capture_output=True, text=True, timeout=5)
    print(f"{cmd}: stdout='{r.stdout.strip()}' stderr='{r.stderr.strip()}' rc={r.returncode}")

# Also try python
r = subprocess.run(["python3", "--version"], capture_output=True, text=True, timeout=5)
print(f"python3: {r.stdout}{r.stderr}")

# Try to pip list
r = subprocess.run(["python3", "-m", "pip", "list", "--format=columns"], capture_output=True, text=True, timeout=10)
print(f"pip list: {r.stdout[:1000]}")
print(f"pip stderr: {r.stderr[:500]}")

# Try pdftotext directly
r = subprocess.run(["pdftotext", "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf", "-"], capture_output=True, text=True, timeout=10)
print(f"\n=== pdftotext output ===")
print(r.stdout[:2000] if r.stdout else "NO STDOUT")
print(f"stderr: {r.stderr[:500]}")
print(f"rc: {r.returncode}")
