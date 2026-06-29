#!/usr/bin/env python3
"""Install pypdf and extract text from the resume PDF."""
import subprocess
import sys

# Try installing pypdf (lightweight, pure Python)
r = subprocess.run(
    [sys.executable, "-m", "pip", "install", "pypdf"],
    capture_output=True, text=True, timeout=30
)
print(f"Install pypdf: rc={r.returncode}")
print(r.stdout[-500:])
print(r.stderr[-500:])

# Now try to extract
if r.returncode == 0:
    from pypdf import PdfReader
    reader = PdfReader("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf")
    print(f"\nTotal pages: {len(reader.pages)}")
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        print(f"\n=== Page {i+1} ===")
        print(text)
