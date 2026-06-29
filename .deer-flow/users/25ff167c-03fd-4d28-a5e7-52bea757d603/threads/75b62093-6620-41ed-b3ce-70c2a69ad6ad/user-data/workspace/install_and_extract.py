#!/usr/bin/env python3
import subprocess

# List all pdf tools
for cmd in ["which pdftotext", "which pdftotext", "dpkg -l | grep poppler", "apt list --installed 2>/dev/null | grep pdf", "which mutool", "which mutool", "pip3 list 2>/dev/null | grep -i pdf"]:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        out = r.stdout.strip()
        if out:
            print(f"[{cmd}] {out[:300]}")
    except:
        pass

# Install pdftotext
print("\n--- Trying to install poppler ---")
r = subprocess.run("apt-get install -y poppler-utils 2>&1 | tail -5", shell=True, capture_output=True, text=True, timeout=60)
print(r.stdout[-300:] if r.stdout else "no output")
print(r.stderr[-300:] if r.stderr else "no stderr")

# Try again
print("\n--- Trying pdftotext again ---")
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
        print(f"Failed: {r.stderr[:500]}")
