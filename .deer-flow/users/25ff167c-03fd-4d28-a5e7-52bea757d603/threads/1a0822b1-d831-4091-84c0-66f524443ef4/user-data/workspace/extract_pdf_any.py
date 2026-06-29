#!/usr/bin/env python3
"""Try multiple approaches to extract PDF content."""
import subprocess
import sys

# Approach 1: Try pdftotext
print("=" * 60)
print("APPROACH 1: pdftotext")
print("=" * 60)
r = subprocess.run(["pdftotext", "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf", "-"], 
                   capture_output=True, text=True, timeout=10)
if r.returncode == 0 and r.stdout.strip():
    print("SUCCESS! Content follows:")
    print(r.stdout)
    sys.exit(0)
else:
    print(f"Failed: rc={r.returncode}, stderr={r.stderr[:200]}")

# Approach 2: Try installing pypdf
print("\n" + "=" * 60)
print("APPROACH 2: pip install pypdf")
print("=" * 60)
r = subprocess.run(
    [sys.executable, "-m", "pip", "install", "pypdf", "--quiet"],
    capture_output=True, text=True, timeout=30
)
print(f"Install result: rc={r.returncode}")
if r.returncode == 0:
    from pypdf import PdfReader
    reader = PdfReader("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf")
    print(f"Pages: {len(reader.pages)}")
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        print(f"\n=== Page {i+1} ===")
        print(text)
    if text.strip():
        sys.exit(0)

# Approach 3: Try pdfminer.six
print("\n" + "=" * 60)
print("APPROACH 3: pip install pdfminer.six")
print("=" * 60)
r = subprocess.run(
    [sys.executable, "-m", "pip", "install", "pdfminer.six", "--quiet"],
    capture_output=True, text=True, timeout=30
)
print(f"Install result: rc={r.returncode}")
if r.returncode == 0:
    from pdfminer.high_level import extract_text
    text = extract_text("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf")
    print(text)
