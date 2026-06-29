#!/usr/bin/env python3
"""Multi-approach PDF extractor."""
import subprocess, sys, os, importlib

path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf"

# Check file exists
print(f"File exists: {os.path.exists(path)}")
print(f"File size: {os.path.getsize(path)} bytes")
print(f"Python: {sys.version}")

# Check what's available
for name in ["pypdf", "PyPDF2", "pdfminer", "fitz", "pdfplumber", "pdfminer.high_level"]:
    try:
        importlib.import_module(name.split('.')[0])
        print(f"✓ {name}")
    except ImportError:
        print(f"✗ {name}")

# Try pypdf install
print("\n--- Installing pypdf ---")
r = subprocess.run(
    [sys.executable, "-m", "pip", "install", "pypdf"],
    capture_output=True, text=True, timeout=30
)
print(r.stdout[-500:])
if r.returncode != 0:
    print(r.stderr[-500:])

try:
    from pypdf import PdfReader
    reader = PdfReader(path)
    print(f"\nTotal pages: {len(reader.pages)}")
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        print(f"\n=== Page {i+1} ===")
        print(text[:2000])
except Exception as e:
    print(f"pypdf error: {e}")
