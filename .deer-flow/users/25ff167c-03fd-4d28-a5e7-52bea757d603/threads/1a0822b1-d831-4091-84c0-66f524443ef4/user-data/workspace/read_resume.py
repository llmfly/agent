#!/usr/bin/env python3
"""Install pypdf and extract text."""
import subprocess
import sys
import importlib

# Try to import pypdf first
try:
    importlib.import_module('pypdf')
    print("pypdf already installed")
except ImportError:
    print("Installing pypdf...")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "pypdf"],
        capture_output=True, text=True, timeout=30
    )
    print(r.stdout[-300:])
    if r.returncode != 0:
        print("STDERR:", r.stderr[-300:])
        sys.exit(1)

from pypdf import PdfReader
reader = PdfReader("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf")
print(f"Total pages: {len(reader.pages)}")
for i, page in enumerate(reader.pages):
    text = page.extract_text()
    print(f"\n--- Page {i+1} ---")
    print(text)
