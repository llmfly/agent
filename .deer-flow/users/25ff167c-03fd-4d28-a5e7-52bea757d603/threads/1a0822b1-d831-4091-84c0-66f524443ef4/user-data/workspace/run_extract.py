#!/usr/bin/env python3
"""Extract resume PDF content using available tools."""
import subprocess
import sys
import os

pdf_path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf"

# Verify file
print(f"File exists: {os.path.exists(pdf_path)}")
print(f"File size: {os.path.getsize(pdf_path)}")

# Try pdftotext
r = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True, timeout=10)
print(f"\npdftotext: rc={r.returncode}, len={len(r.stdout)}")
if r.returncode == 0 and r.stdout.strip():
    print(r.stdout[:5000])
    sys.exit(0)

# Try installing pypdf
print("\n\nTrying pypdf...")
r = subprocess.run([sys.executable, "-m", "pip", "install", "pypdf"], capture_output=True, text=True, timeout=30)
if r.returncode == 0:
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    print(f"Pages: {len(reader.pages)}")
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        print(f"\n=== Page {i+1} ===")
        print(text[:3000])
