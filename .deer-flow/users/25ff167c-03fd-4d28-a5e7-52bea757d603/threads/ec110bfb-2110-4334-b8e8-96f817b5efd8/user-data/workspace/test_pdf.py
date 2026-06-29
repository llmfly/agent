#!/usr/bin/env python3
import subprocess, sys, os

print("Python:", sys.executable)

# Install pymupdf
result = subprocess.run([sys.executable, "-m", "pip", "install", "pymupdf"], capture_output=True, text=True)
print("STDOUT:", result.stdout[-200:])
print("STDERR:", result.stderr[-200:])
print("Return:", result.returncode)

import fitz
print("fitz imported successfully")

fpath = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/ec110bfb-2110-4334-b8e8-96f817b5efd8/user-data/uploads/崔亚飞.pdf"
doc = fitz.open(fpath)
print(f"Pages: {doc.page_count}")
for i, page in enumerate(doc):
    text = page.get_text()
    print(f"Page {i+1}: {len(text)} chars")
    if i == 0:
        print(text[:1000])
doc.close()
