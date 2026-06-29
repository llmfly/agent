#!/usr/bin/env python3
"""Extract PDF content using standard library approach."""
import subprocess, sys, os

# Check what's available
print("Python:", sys.executable)

# First, let's try to use python3 with subprocess to install a PDF reader
result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "PyMuPDF", "-q"],
    capture_output=True, text=True, timeout=120
)
print("pip install:", result.returncode, result.stderr[:200])

# If install succeeds, try extracting
if result.returncode == 0:
    extract_code = """
import fitz
doc = fitz.open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/2f424c6d-41c4-4383-9882-691f9a132244/user-data/uploads/杨佳文-java后端-v8.pdf")
print(f"Pages: {doc.page_count}")
for i in range(doc.page_count):
    text = doc[i].get_text()
    print(f"=== Page {i+1} ===")
    print(text if text.strip() else "(no text)")
doc.close()
"""
    result2 = subprocess.run(
        [sys.executable, "-c", extract_code],
        capture_output=True, text=True, timeout=30
    )
    print("Extract stdout:", result2.stdout[:3000])
    print("Extract stderr:", result2.stderr[:500])
else:
    print("Install failed, trying alternatives...")
    # Try pdfminer
    result3 = subprocess.run(
        [sys.executable, "-m", "pip", "install", "pdfminer.six", "-q"],
        capture_output=True, text=True, timeout=60
    )
    print("pdfminer install:", result3.returncode)
    
    if result3.returncode == 0:
        extract_code2 = """
from pdfminer.high_level import extract_text
text = extract_text("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/2f424c6d-41c4-4383-9882-691f9a132244/user-data/uploads/杨佳文-java后端-v8.pdf")
print(text[:3000])
"""
        result4 = subprocess.run(
            [sys.executable, "-c", extract_code2],
            capture_output=True, text=True, timeout=30
        )
        print("pdfminer stdout:", result4.stdout[:3000])
        print("pdfminer stderr:", result4.stderr[:500])
