#!/usr/bin/env python3
"""Try to extract PDF using pdftotext."""
import subprocess
import os

pdf_path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf"

print(f"File exists: {os.path.exists(pdf_path)}")
print(f"File size: {os.path.getsize(pdf_path)} bytes")

# Method 1: pdftotext
print("\n=== Method 1: pdftotext ===")
r = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True, timeout=10)
print(f"Return code: {r.returncode}")
if r.returncode == 0 and r.stdout.strip():
    print(r.stdout[:5000])
else:
    print(f"stdout: '{r.stdout[:300]}'")
    print(f"stderr: '{r.stderr[:300]}'")

# Method 2: Try installing something
print("\n=== Method 2: Try pip install pypdf ===")
r2 = subprocess.run(["python3", "-m", "pip", "install", "pypdf", "--quiet"], 
                     capture_output=True, text=True, timeout=30)
print(f"pip rc: {r2.returncode}")
if r2.returncode == 0:
    print("pypdf installed successfully")
