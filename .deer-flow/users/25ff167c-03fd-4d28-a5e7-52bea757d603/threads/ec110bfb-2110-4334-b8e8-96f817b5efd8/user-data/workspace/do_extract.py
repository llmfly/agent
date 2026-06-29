#!/usr/bin/env python3
import subprocess, sys

print("sys.executable:", sys.executable, file=sys.stderr)

# Install pymupdf
r = subprocess.run([sys.executable, "-m", "pip", "install", "pymupdf"], capture_output=True, text=True)
print("Install:", r.returncode, file=sys.stderr)
if r.stderr:
    print("STDERR:", r.stderr[-300:], file=sys.stderr)
if r.stdout:
    print("STDOUT:", r.stdout[-300:], file=sys.stderr)

# Extract
import fitz
doc = fitz.open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/ec110bfb-2110-4334-b8e8-96f817b5efd8/user-data/uploads/崔亚飞.pdf")
for page in doc:
    print(page.get_text()[:2000])
doc.close()
