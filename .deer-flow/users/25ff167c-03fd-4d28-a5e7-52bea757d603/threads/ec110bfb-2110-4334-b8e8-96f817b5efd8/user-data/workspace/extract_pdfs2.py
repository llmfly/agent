#!/usr/bin/env python3
"""Extract text from PDFs using PyMuPDF"""
import subprocess, sys, os

result = subprocess.run([sys.executable, "-m", "pip", "install", "pymupdf", "-q"], capture_output=True, text=True)
print("PyMuPDF install:", result.returncode)

import fitz

for fpath in ["/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/ec110bfb-2110-4334-b8e8-96f817b5efd8/user-data/uploads/崔亚飞.pdf", "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/ec110bfb-2110-4334-b8e8-96f817b5efd8/user-data/uploads/杨佳文-java后端-v8.pdf"]:
    print(f"\n{'='*80}")
    print(f"File: {os.path.basename(fpath)}")
    print(f"{'='*80}")
    doc = fitz.open(fpath)
    print(f"Pages: {doc.page_count}")
    text = ""
    for page in doc:
        text += page.get_text()
    outpath = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/ec110bfb-2110-4334-b8e8-96f817b5efd8/user-data/workspace/{os.path.basename(fpath).replace('.pdf', '.txt')}"
    with open(outpath, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Total chars: {len(text)}")
    print(text[:3000])
    doc.close()
