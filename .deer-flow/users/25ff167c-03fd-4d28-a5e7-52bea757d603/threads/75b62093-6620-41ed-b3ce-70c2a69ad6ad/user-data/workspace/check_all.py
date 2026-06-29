#!/usr/bin/env python3
"""Check available Python libraries and system tools for PDF processing."""
import subprocess, importlib, os

# Check Python modules
modules_to_check = ["PyMuPDF", "fitz", "pdfminer", "pdfminer.high_level", "pdfplumber", "pypdf", "pdfminer", "pdfminer3", "pdfminer.high_level", "pdfminer.pdfinterp", "camelot", "tabula", "pdfminer.converter", "pdfminer.layout"]
print("=== Python PDF modules ===")
for mod in modules_to_check:
    try:
        m = importlib.import_module(mod.split('.')[0])
        loc = getattr(m, '__file__', 'unknown')
        print(f"  {mod}: AVAILABLE at {loc}")
    except ImportError:
        print(f"  {mod}: not available")

# Check system tools
print("\n=== System tools ===")
for cmd in ["pdftotext", "pdftotext", "mutool", "pdftotext"]:
    r = subprocess.run(["which", cmd], capture_output=True, text=True)
    print(f"  {cmd}: {r.stdout.strip() or 'NOT FOUND'}")

# Check for poppler
r = subprocess.run(["dpkg", "-l"], capture_output=True, text=True, timeout=30)
if 'poppler' in r.stdout:
    print("\npoppler-utils: INSTALLED")
else:
    print("\npoppler-utils: NOT INSTALLED")

# Try installing
print("\n=== Trying to install poppler-utils ===")
r = subprocess.run(["apt-get", "update", "-qq"], capture_output=True, text=True, timeout=60)
print(f"apt update: return={r.returncode}")
r = subprocess.run(["apt-get", "install", "-y", "-qq", "poppler-utils"], capture_output=True, text=True, timeout=120)
print(f"apt install: return={r.returncode}")
if r.stderr:
    print(f"stderr: {r.stderr[:300]}")

r = subprocess.run(["which", "pdftotext"], capture_output=True, text=True)
print(f"pdftotext now: {r.stdout.strip() or 'STILL NOT FOUND'}")
