#!/usr/bin/env python3
"""Extract text from PDF file using available libraries."""
import sys

# Try PyMuPDF (fitz)
try:
    import fitz
    doc = fitz.open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/4701a749-5761-463e-b5d0-8719d0d7c800/user-data/uploads/1201060226271-2Pys.pdf")
    with open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/4701a749-5761-463e-b5d0-8719d0d7c800/user-data/workspace/pdf_output.txt", "w", encoding="utf-8") as f:
        f.write(f"Total pages: {doc.page_count}\n\n")
        for page_num in range(doc.page_count):
            page = doc[page_num]
            text = page.get_text()
            f.write(f"--- Page {page_num+1} ---\n")
            f.write(text)
            f.write("\n\n")
    doc.close()
    print("SUCCESS: Extracted using PyMuPDF")
    sys.exit(0)
except ImportError:
    pass

# Try pdfminer
try:
    from pdfminer.high_level import extract_text_to_fp
    from io import StringIO
    output = StringIO()
    with open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/4701a749-5761-463e-b5d0-8719d0d7c800/user-data/uploads/1201060226271-2Pys.pdf", "rb") as f:
        extract_text_to_fp(f, output)
    with open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/4701a749-5761-463e-b5d0-8719d0d7c800/user-data/workspace/pdf_output.txt", "w", encoding="utf-8") as f:
        f.write(output.getvalue())
    print("SUCCESS: Extracted using pdfminer")
    sys.exit(0)
except ImportError:
    pass

# Try PyPDF2
try:
    import PyPDF2
    with open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/4701a749-5761-463e-b5d0-8719d0d7c800/user-data/uploads/1201060226271-2Pys.pdf", "rb") as f:
        reader = PyPDF2.PdfReader(f)
        with open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/4701a749-5761-463e-b5d0-8719d0d7c800/user-data/workspace/pdf_output.txt", "w", encoding="utf-8") as fout:
            fout.write(f"Total pages: {len(reader.pages)}\n\n")
            for i, page in enumerate(reader.pages):
                fout.write(f"--- Page {i+1} ---\n")
                fout.write(page.extract_text())
                fout.write("\n\n")
    print("SUCCESS: Extracted using PyPDF2")
    sys.exit(0)
except ImportError:
    pass

# Try pdfplumber
try:
    import pdfplumber
    with pdfplumber.open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/4701a749-5761-463e-b5d0-8719d0d7c800/user-data/uploads/1201060226271-2Pys.pdf") as pdf:
        with open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/4701a749-5761-463e-b5d0-8719d0d7c800/user-data/workspace/pdf_output.txt", "w", encoding="utf-8") as f:
            f.write(f"Total pages: {len(pdf.pages)}\n\n")
            for i, page in enumerate(pdf.pages):
                f.write(f"--- Page {i+1} ---\n")
                f.write(page.extract_text() or "")
                f.write("\n\n")
    print("SUCCESS: Extracted using pdfplumber")
    sys.exit(0)
except ImportError:
    pass

print("NO_PDF_LIBRARY_AVAILABLE")
