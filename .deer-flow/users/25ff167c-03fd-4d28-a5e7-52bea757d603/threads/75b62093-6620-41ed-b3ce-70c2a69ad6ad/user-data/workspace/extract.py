#!/usr/bin/env python3
import subprocess
import sys

for fname in ["崔亚飞.pdf", "杨佳文-java后端-v8.pdf"]:
    path = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/75b62093-6620-41ed-b3ce-70c2a69ad6ad/user-data/uploads/{fname}"
    print(f"\n{'='*60}")
    print(f"FILE: {fname}")
    print('='*60)
    
    try:
        r = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            text = r.stdout
            print(f"Length: {len(text)} chars")
            print(text[:8000])
            if len(text) > 8000:
                print(f"\n... [truncated, {len(text)} total chars]")
        else:
            print(f"Return code: {r.returncode}, Stderr: {r.stderr[:200]}")
    except Exception as e:
        print(f"Error: {e}")
