#!/usr/bin/env python3
import subprocess
import os
import sys

os.chdir('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace')

# Check for pdftotext
r = subprocess.run('which pdftotext', capture_output=True, text=True, timeout=10, shell=True)
sys.stdout.write("which pdftotext: " + (r.stdout.strip() or "NOT FOUND") + "\n")

# Check python
r = subprocess.run('python3 -m pip list', capture_output=True, text=True, timeout=15, shell=True)
sys.stdout.write(r.stdout[:3000] + "\n")
if r.stderr:
    sys.stdout.write("STDERR: " + r.stderr[:500] + "\n")

sys.stdout.flush()
