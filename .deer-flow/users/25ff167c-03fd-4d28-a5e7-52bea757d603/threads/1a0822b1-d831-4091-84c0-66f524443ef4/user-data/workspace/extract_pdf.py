#!/usr/bin/env python3
"""Extract PDF content using pdftotext."""
import subprocess
import sys

# Try pdftotext
r = subprocess.run(["which", "pdftotext"], capture_output=True, text=True, timeout=5)
print(f"which pdftotext: rc={r.returncode}, out='{r.stdout.strip()}', err='{r.stderr}'")

r = subprocess.run(["pdftotext", "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf", "-"], 
                   capture_output=True, text=True, timeout=10)
print(f"pdftotext rc={r.returncode}")
print(f"stdout len={len(r.stdout)}")
print(f"stderr='{r.stderr[:300]}'")
if r.stdout:
    print("CONTENT:")
    print(r.stdout[:5000])
