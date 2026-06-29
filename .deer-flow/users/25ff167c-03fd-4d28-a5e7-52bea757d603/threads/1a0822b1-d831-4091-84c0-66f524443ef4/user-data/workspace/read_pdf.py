#!/usr/bin/env python3
"""Minimal script to just install pypdf and extract."""
import subprocess
import sys

subprocess.run([sys.executable, "-m", "pip", "install", "pypdf"], 
               capture_output=True, text=True, timeout=30)

from pypdf import PdfReader
reader = PdfReader("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf")
print(f"Pages: {len(reader.pages)}")
full_text = ""
for i, page in enumerate(reader.pages):
    text = page.extract_text()
    full_text += text + "\n"
    print(f"\n=== Page {i+1} ===")
    print(text)

print("\n\n=== FULL TEXT ===")
print(full_text)
