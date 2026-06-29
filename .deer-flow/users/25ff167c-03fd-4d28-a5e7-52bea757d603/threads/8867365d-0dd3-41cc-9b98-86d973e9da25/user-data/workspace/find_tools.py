import subprocess, sys

# Hail Mary - try all possible commands
for cmd in [["pdftotext"], ["mutool", "draw"], ["mutool", "draw", "-F", "text"], ["pdfinfo"]]:
    try:
        r = subprocess.run([cmd[0], "--version"] if cmd[0] == "pdftotext" else [cmd[0], "-v"], capture_output=True, text=True, timeout=5)
        print(f"{cmd[0]}: available - {r.stdout[:100]}")
    except:
        print(f"{cmd[0]}: NOT available")

# Also try python
print("\nPython packages:")
r = subprocess.run([sys.executable, "-m", "pip", "list", "--format=columns"], capture_output=True, text=True, timeout=10)
lines = r.stdout.split('\n')
for line in lines:
    if any(pkg in line.lower() for pkg in ['pdf', 'pypdf', 'pdfminer', 'pdfplumber', 'pymupdf', 'muPDF', 'fitz', 'pdf2image']):
        print(f"  {line}")

if not any(pkg in r.stdout.lower() for pkg in ['pdf', 'pypdf']):
    print("No PDF packages found. Trying to install pypdf...")
    r2 = subprocess.run([sys.executable, "-m", "pip", "install", "pypdf"], capture_output=True, text=True, timeout=30)
    print(r2.stdout[-200:])
    print(r2.stderr[-200:])
