#!/usr/bin/env python3
import subprocess, os

os.chdir('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace')

# Try installing pip packages instead
r = subprocess.run(
    "pip3 install pdfminer.six 2>&1 | tail -5",
    shell=True, capture_output=True, text=True, timeout=60
)
print(r.stdout)
print(r.stderr)

# Now try to extract
r = subprocess.run(
    "python3 -c \"from pdfminer.high_level import extract_text; text = extract_text('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/uploads/崔亚飞.pdf'); print(text[:5000])\"",
    shell=True, capture_output=True, text=True, timeout=60
)
print(r.stdout[:5000])
print(r.stderr[:500])
