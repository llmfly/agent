#!/usr/bin/env python3
"""Simple test script."""
print("Hello from Python!")
import sys
print(f"Python version: {sys.version}")

import subprocess
r = subprocess.run(["which", "pdftotext"], capture_output=True, text=True)
print(f"pdftotext: {r.stdout.strip() or 'not found'}")

r = subprocess.run(["which", "python3"], capture_output=True, text=True)
print(f"python3: {r.stdout.strip() or 'not found'}")
