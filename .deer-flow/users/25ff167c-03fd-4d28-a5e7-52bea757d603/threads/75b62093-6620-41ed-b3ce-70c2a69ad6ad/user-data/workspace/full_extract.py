#!/usr/bin/env python3
import subprocess

# Install poppler-utils
print("Installing poppler-utils...")
r = subprocess.run("apt-get update -qq && apt-get install -y -qq poppler-utils 2>&1 | tail -3", shell=True, capture_output=True, text=True, timeout=120)
print(r.stdout)
print(r.stderr[:200] if r.stderr else "")

# Try pdftotext
print("\n--- Extracting PDFs ---")
for fname in ["崔亚飞.pdf", "杨佳文-java后端-v8.pdf"]:
    path = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/75b62093-6620-41ed-b3ce-70c2a69ad6ad/user-data/uploads/{fname}"
    print(f"\n{'='*60}")
    print(f"FILE: {fname}")
    r = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, timeout=30)
    if r.returncode == 0 and r.stdout.strip():
        text = r.stdout
        print(f"Extracted {len(text)} chars")
        print(text)
    else:
        print(f"Failed: {r.stderr[:300]}")
