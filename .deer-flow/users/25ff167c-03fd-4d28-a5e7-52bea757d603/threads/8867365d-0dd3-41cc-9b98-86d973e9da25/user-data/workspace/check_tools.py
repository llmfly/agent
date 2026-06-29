import subprocess
import sys

# Check tools
for exe in ["pdftotext", "mutool", "python3"]:
    r = subprocess.run(["which", exe], capture_output=True, text=True)
    print(f"{exe}: {r.stdout.strip() or 'NOT FOUND'}")

# Check python modules
for mod in ["PyPDF2", "pypdf", "pdfminer", "pdfplumber", "pdfminer.high_level"]:
    try:
        exec(f"import {mod}")
        print(f"{mod}: available")
    except Exception as e:
        print(f"{mod}: {str(e)[:50]}")
