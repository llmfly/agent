#!/usr/bin/env python3
"""Copy PDF to workspace and install pypdf."""
import subprocess, os, shutil

# Copy PDF to workspace
src = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf"
dst = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/workspace/resume.pdf"
shutil.copy2(src, dst)
print(f"Copied to {dst}, size={os.path.getsize(dst)}")

# Try pdftotext
r = subprocess.run(["pdftotext", dst, "-"], capture_output=True, text=True, timeout=10)
print(f"pdftotext: rc={r.returncode}, len={len(r.stdout)}")
if r.stdout:
    print(r.stdout[:5000])
