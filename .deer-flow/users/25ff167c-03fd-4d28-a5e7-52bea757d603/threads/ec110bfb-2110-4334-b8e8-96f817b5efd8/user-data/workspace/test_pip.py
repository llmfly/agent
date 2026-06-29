#!/usr/bin/env python3
import subprocess, sys, os

print("Python:", sys.executable)

result = subprocess.run([sys.executable, "-m", "pip", "install", "pymupdf"], capture_output=False, text=True)
print("Return:", result.returncode)
