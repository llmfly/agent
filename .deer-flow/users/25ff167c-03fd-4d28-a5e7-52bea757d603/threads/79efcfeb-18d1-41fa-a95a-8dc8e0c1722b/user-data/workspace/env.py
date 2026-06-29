#!/usr/bin/env python3
import subprocess, os, sys

os.chdir('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace')

# Simple approach - use subprocess with shell=True
result = subprocess.run("which pdftotext", shell=True, capture_output=True, text=True, timeout=10)
print("WHICH:", repr(result.stdout), repr(result.stderr))

result = subprocess.run("python3 -m pip list 2>&1 | head -50", shell=True, capture_output=True, text=True, timeout=15)
print("PIP LIST:", result.stdout[:3000])
