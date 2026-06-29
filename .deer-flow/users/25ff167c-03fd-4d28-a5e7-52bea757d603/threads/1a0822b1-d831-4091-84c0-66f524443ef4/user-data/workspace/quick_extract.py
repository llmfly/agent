#!/usr/bin/env python3
"""Quick PDF extraction test."""
import subprocess, os

pdf = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf"
print(f"exists={os.path.exists(pdf)}, size={os.path.getsize(pdf)}")

# Try pdftotext
r = subprocess.run(["pdftotext", pdf, "-"], capture_output=True, text=True, timeout=10)
print(f"pdftotext: rc={r.returncode}, len={len(r.stdout)}, err={r.stderr[:200]}")
if r.stdout:
    print(r.stdout[:3000])
