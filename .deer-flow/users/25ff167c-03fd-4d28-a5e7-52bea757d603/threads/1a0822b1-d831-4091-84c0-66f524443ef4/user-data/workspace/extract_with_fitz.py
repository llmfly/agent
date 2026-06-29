#!/usr/bin/env python3
"""Try installing PyMuPDF (fitz) and extracting text."""
import subprocess
import sys

# Try fitz first (light)
r = subprocess.run(
    [sys.executable, "-m", "pip", "install", "PyMuPDF", "--quiet"],
    capture_output=True, text=True, timeout=60
)
print(f"Install PyMuPDF: rc={r.returncode}")
print(r.stdout[-200:])
print(r.stderr[-200:])

if r.returncode == 0:
    import fitz
    doc = fitz.open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf")
    print(f"Pages: {doc.page_count}")
    for i, page in enumerate(doc):
        text = page.get_text()
        print(f"\n=== Page {i+1} ===")
        print(text)
else:
    # Fallback to pypdf
    r2 = subprocess.run(
        [sys.executable, "-m", "pip", "install", "pypdf", "--quiet"],
        capture_output=True, text=True, timeout=30
    )
    print(f"Install pypdf: rc={r2.returncode}")
    if r2.returncode == 0:
        from pypdf import PdfReader
        reader = PdfReader("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf")
        print(f"Pages: {len(reader.pages)}")
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            print(f"\n=== Page {i+1} ===")
            print(text)
