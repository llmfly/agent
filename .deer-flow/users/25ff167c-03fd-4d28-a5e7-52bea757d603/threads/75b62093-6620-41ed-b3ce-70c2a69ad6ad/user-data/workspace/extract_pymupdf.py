#!/usr/bin/env python3
import subprocess, sys

print("=== Checking Python packages ===")
r = subprocess.run([sys.executable, "-m", "pip", "list", "--format=columns"], capture_output=True, text=True, timeout=30)
lines = r.stdout.split('\n')
pdf_related = [l for l in lines if any(x in l.lower() for x in ['pdf', 'fitz', 'muPDF', 'pdfminer', 'pdfplumber', 'tika', 'camelot', 'tabula'])]
print("PDF packages found:", pdf_related)

print("\n=== Trying to install PyMuPDF ===")
r = subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF", "-q"], capture_output=True, text=True, timeout=60)
print("Return:", r.returncode)
print("Stderr:", r.stderr[:300])

print("\n=== Now extracting ===")
try:
    import fitz
    for fname in ["崔亚飞.pdf", "杨佳文-java后端-v8.pdf"]:
        path = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/75b62093-6620-41ed-b3ce-70c2a69ad6ad/user-data/uploads/{fname}"
        print(f"\n{'='*60}")
        print(f"FILE: {fname}")
        doc = fitz.open(path)
        print(f"Pages: {len(doc)}")
        for page in doc:
            text = page.get_text()
            print(text)
except Exception as e:
    print(f"PyMuPDF error: {e}")
    import traceback
    traceback.print_exc()
