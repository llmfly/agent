#!/usr/bin/env python3
"""Extract text from PDF files using available tools."""
import subprocess
import os

# Check what's available
for cmd in ["pdftotext", "pdfinfo", "mutool", "python3"]:
    try:
        r = subprocess.run(["which", cmd], capture_output=True, text=True)
        if r.stdout.strip():
            print(f"Found: {r.stdout.strip()}")
    except:
        pass

# Try pdftotext
for fname in ["崔亚飞.pdf", "杨佳文-java后端-v8.pdf"]:
    path = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/75b62093-6620-41ed-b3ce-70c2a69ad6ad/user-data/uploads/{fname}"
    print(f"\n{'='*70}")
    print(f"FILE: {fname}")
    print('='*70)
    
    # Try pdftotext
    try:
        r = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            text = r.stdout
            print(f"[pdftotext] Extracted {len(text)} chars")
            print(text[:6000])
            if len(text) > 6000:
                print(f"\n... [truncated, {len(text)} total chars]")
            continue
    except Exception as e:
        print(f"pdftotext failed: {e}")
    
    # Try python with PyMuPDF
    try:
        r = subprocess.run([sys.executable, "-c", f"""
import fitz
doc = fitz.open('{path}')
for page in doc:
    print(page.get_text())
""" if False else ""], capture_output=True, text=True, timeout=30)
    except:
        pass
    
    print("Could not extract text from this PDF")
