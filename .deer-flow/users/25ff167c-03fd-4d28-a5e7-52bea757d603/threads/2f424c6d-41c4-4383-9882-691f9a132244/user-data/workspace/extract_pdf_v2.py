#!/usr/bin/env python3
import subprocess, sys, os

# Check available tools
for cmd in ["pdftotext", "python3"]:
    r = subprocess.run(["which", cmd], capture_output=True, text=True)
    print(f"{cmd}: {r.stdout.strip() or 'NOT FOUND'}")

print(f"Python: {sys.executable}")

# Just try to import fitz directly (may already be installed by prior attempts)
r = subprocess.run(
    [sys.executable, "-c", "import fitz; print('fitz OK')"],
    capture_output=True, text=True, timeout=10
)
print(f"fitz check: {r.returncode}, {r.stdout}, {r.stderr[:200]}")

if r.returncode != 0:
    # Install
    subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF"], capture_output=True, text=True, timeout=60)
    r2 = subprocess.run([sys.executable, "-c", "import fitz; print('fitz OK')"], capture_output=True, text=True, timeout=10)
    print(f"fitz after install: {r2.returncode}, {r2.stdout}, {r2.stderr[:200]}")

# Try extraction
r3 = subprocess.run(
    [sys.executable, "-c", """
import fitz
doc = fitz.open('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/2f424c6d-41c4-4383-9882-691f9a132244/user-data/uploads/杨佳文-java后端-v8.pdf')
print('Pages:', doc.page_count)
for i in range(doc.page_count):
    text = doc[i].get_text()
    print('=== Page', i+1, '===')
    print(text if text.strip() else '(no text)')
doc.close()
"""],
    capture_output=True, text=True, timeout=30
)
print(f"Extract return: {r3.returncode}")
if r3.stdout:
    print(r3.stdout[:8000])
if r3.stderr:
    print("STDERR:", r3.stderr[:1000])
