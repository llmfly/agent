#!/usr/bin/env python3
import subprocess, os

os.chdir('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace')

# Check pdftotext
r = subprocess.run(['which', 'pdftotext'], capture_output=True, text=True)
has_pdftotext = r.stdout.strip()

# Try pdftotext on 崔亚飞
if has_pdftotext:
    r = subprocess.run(['pdftotext', '-layout', '/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/uploads/崔亚飞.pdf', '-'], 
                       capture_output=True, text=True, timeout=30)
    print("=== 崔亚飞.pdf ===")
    print(r.stdout[:6000] if r.stdout else "EMPTY")
    if r.stderr:
        print("STDERR:", r.stderr[:500])
else:
    print("pdftotext not found, trying python...")
    # Check if there's a python library
    r = subprocess.run(['python3', '-c', '''
import subprocess
r = subprocess.run(["pdftotext", "--version"], capture_output=True, text=True)
print(r.stdout[:200])
print(r.stderr[:200])
'''], capture_output=True, text=True, timeout=10)
    print(r.stdout[:500])
    print(r.stderr[:500])
