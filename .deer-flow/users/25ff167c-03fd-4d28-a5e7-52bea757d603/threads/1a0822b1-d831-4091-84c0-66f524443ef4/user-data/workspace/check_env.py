#!/usr/bin/env python3
"""Extract text from PDF using pdftotext or python libraries."""
import subprocess
import sys

def check_tools():
    """Check available PDF extraction tools."""
    # Check for pdftotext
    try:
        r = subprocess.run(["which", "pdftotext"], capture_output=True, text=True, timeout=5)
        print(f"pdftotext: {'FOUND at ' + r.stdout.strip() if r.returncode == 0 else 'NOT FOUND'}")
    except Exception as e:
        print(f"pdftotext check error: {e}")

    # Check python version
    print(f"Python: {sys.version}")

    # Check for pdfminer / pypdf / pdfplumber
    for mod in ["pdfminer", "PyPDF2", "pypdf", "pdfplumber", "pdfminer.high_level", "pdfminer3"]:
        r = subprocess.run(
            [sys.executable, "-c", f"import {mod.split('.')[0]}"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            print(f"Module {mod}: AVAILABLE")
        else:
            print(f"Module {mod}: not available")

    # Try installing pdftotext via apt
    r = subprocess.run(["apt-get", "--version"], capture_output=True, text=True, timeout=5)
    print(f"apt-get: {'AVAILABLE' if r.returncode == 0 else 'NOT AVAILABLE'}")

if __name__ == "__main__":
    check_tools()
