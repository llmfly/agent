#!/usr/bin/env python3
import subprocess, sys

# Show what python packages are available
r = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True, timeout=30)
print(r.stdout)

# Try import common PDF libs
for mod in ["PyMuPDF", "fitz", "pdfminer", "pdfplumber", "pypdf", "pdfminer.high_level", "pdfminer"]:
    try:
        exec(f"import {mod.split('.')[0]}")
        print(f"  {mod} - available")
    except ImportError:
        print(f"  {mod} - not available")
