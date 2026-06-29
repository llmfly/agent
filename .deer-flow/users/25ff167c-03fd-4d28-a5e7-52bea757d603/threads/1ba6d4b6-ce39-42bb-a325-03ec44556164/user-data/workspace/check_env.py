#!/usr/bin/env python3
"""Check available Python and PDF libraries."""
import subprocess
import sys

# Check python
result = subprocess.run(["python3", "--version"], capture_output=True, text=True)
print(f"Python3: {result.stdout.strip()}")

# Check available libraries
libs = ["PyPDF2", "pypdf", "pdfminer", "fitz", "pdfplumber", "pdfminer.high_level", "pdfminer.pdfinterp"]
for lib in libs:
    result = subprocess.run(["python3", "-c", f"import {lib.split('.')[0]}; print('ok')"], 
                          capture_output=True, text=True)
    print(f"{lib}: {'AVAILABLE' if result.returncode == 0 else 'NOT AVAILABLE'}")

# Check pdftotext
result = subprocess.run(["which", "pdftotext"], capture_output=True, text=True)
print(f"pdftotext: {'AVAILABLE at ' + result.stdout.strip() if result.returncode == 0 else 'NOT AVAILABLE'}")

# Check pdfinfo
result = subprocess.run(["which", "pdfinfo"], capture_output=True, text=True)
print(f"pdfinfo: {'AVAILABLE at ' + result.stdout.strip() if result.returncode == 0 else 'NOT AVAILABLE'}")
