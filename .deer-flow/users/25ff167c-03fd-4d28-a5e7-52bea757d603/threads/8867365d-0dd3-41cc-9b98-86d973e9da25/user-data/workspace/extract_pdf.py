import subprocess
for exe in ["pdftotext", "mutool", "mutool", "python3"]:
    r = subprocess.run(["which", exe], capture_output=True, text=True)
    print(f"{exe}: {r.stdout.strip() or 'NOT FOUND'}")
for mod in ["PyPDF2", "pypdf", "pdfminer", "pdfplumber"]:
    try:
        exec(f"import {mod}")
        print(f"{mod}: available")
    except:
        print(f"{mod}: not available")
