#!/usr/bin/env python3
"""Extract text from PDF using available libraries."""
import sys
import subprocess

pdf_path = sys.argv[1]

# Method 1: pdftotext
try:
    result = subprocess.run(["pdftotext", "-layout", pdf_path, "-"], 
                          capture_output=True, text=True, timeout=30)
    if result.returncode == 0 and result.stdout.strip():
        print(result.stdout)
        sys.exit(0)
except Exception:
    pass

# Method 2: PyMuPDF (fitz)
try:
    import fitz
    doc = fitz.open(pdf_path)
    for page in doc:
        print(page.get_text())
    sys.exit(0)
except ImportError:
    pass

# Method 3: pdfminer.six
try:
    from pdfminer.high_level import extract_text
    text = extract_text(pdf_path)
    if text.strip():
        print(text)
        sys.exit(0)
except ImportError:
    pass

# Method 4: pypdf
try:
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    for page in reader.pages:
        print(page.extract_text())
    sys.exit(0)
except ImportError:
    pass

# Method 5: pdfplumber
try:
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                print(text)
    sys.exit(0)
except ImportError:
    pass

print("NO_PDF_LIBRARY_AVAILABLE")
sys.exit(1)
