#!/usr/bin/env python3
"""Extract PDF content and generate analysis report."""
import subprocess, sys, os, json, re

pdf_path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/2f424c6d-41c4-4383-9882-691f9a132244/user-data/uploads/杨佳文-java后端-v8.pdf"
output_path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/2f424c6d-41c4-4383-9882-691f9a132244/user-data/outputs/简历分析报告.md"

# Try to install and use PyMuPDF
try:
    import fitz
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF"], capture_output=True, timeout=60)
    import fitz

# Extract text from PDF
doc = fitz.open(pdf_path)
pages_text = []
for i in range(doc.page_count):
    text = doc[i].get_text()
    pages_text.append({"page": i+1, "text": text})
doc.close()

# Save raw text for reference
with open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/2f424c6d-41c4-4383-9882-691f9a132244/user-data/workspace/raw_text.json", "w", encoding="utf-8") as f:
    json.dump(pages_text, f, ensure_ascii=False, indent=2)

# Print all text to stdout
for p in pages_text:
    print(f"\n=== Page {p['page']} ===")
    print(p['text'] if p['text'].strip() else "(empty)")
