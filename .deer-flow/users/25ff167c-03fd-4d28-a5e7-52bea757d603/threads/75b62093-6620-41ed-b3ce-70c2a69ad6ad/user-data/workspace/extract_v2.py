#!/usr/bin/env python3
import subprocess, sys

# Install poppler
r = subprocess.run(["apt-get", "update", "-qq"], capture_output=True, text=True, timeout=60)
r2 = subprocess.run(["apt-get", "install", "-y", "-qq", "poppler-utils"], capture_output=True, text=True, timeout=120)
print("Install result:", r2.returncode, r2.stderr[:200])

# Try pdftotext
r3 = subprocess.run(["which", "pdftotext"], capture_output=True, text=True)
print("pdftotext:", r3.stdout)

if r3.stdout.strip():
    for fname in ["崔亚飞.pdf", "杨佳文-java后端-v8.pdf"]:
        path = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/75b62093-6620-41ed-b3ce-70c2a69ad6ad/user-data/uploads/{fname}"
        print(f"\n{'='*60}")
        print(f"FILE: {fname}")
        r4 = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, timeout=30)
        if r4.returncode == 0 and r4.stdout.strip():
            print(r4.stdout)
        else:
            print("Failed:", r4.stderr[:300])
else:
    print("pdftotext not found, trying pip install...")
    r5 = subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF", "-q"], capture_output=True, text=True, timeout=60)
    print("pip install:", r5.returncode, r5.stderr[:200])
    
    # Try PyMuPDF
    for fname in ["崔亚飞.pdf", "杨佳文-java后端-v8.pdf"]:
        path = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/75b62093-6620-41ed-b3ce-70c2a69ad6ad/user-data/uploads/{fname}"
        print(f"\n{'='*60}")
        print(f"FILE: {fname}")
        try:
            import fitz
            doc = fitz.open(path)
            for page in doc:
                print(page.get_text())
        except Exception as e:
            print(f"PyMuPDF error: {e}")
