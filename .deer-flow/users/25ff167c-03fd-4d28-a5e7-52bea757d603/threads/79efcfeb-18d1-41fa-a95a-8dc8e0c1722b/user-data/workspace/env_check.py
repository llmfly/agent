#!/usr/bin/env python3
import subprocess, os

os.chdir('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace')

# Check pdftotext
r = subprocess.run(['which', 'pdftotext'], capture_output=True, text=True)
print("pdftotext at:", r.stdout.strip() or "NOT FOUND")

# Check if we can find it elsewhere
r = subprocess.run(['find', '/usr', '-name', 'pdftotext', '-type', 'f'], capture_output=True, text=True, timeout=10)
print("find pdftotext:", r.stdout[:500] or "NOT FOUND")

# Check python
r = subprocess.run(['python3', '-c', 'import sys; print(sys.executable)'], capture_output=True, text=True)
print("python:", r.stdout.strip())

# List all python packages
r = subprocess.run(['python3', '-m', 'pip', 'freeze'], capture_output=True, text=True)
print("PIP packages:")
print(r.stdout[:3000])
