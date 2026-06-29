#!/usr/bin/env python3
import subprocess, os

os.chdir('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace')

# Install pdftotext or pdfminer
result = subprocess.run("apt-get update -qq && apt-get install -y -qq poppler-utils 2>&1 | tail -5", shell=True, timeout=60)
print("Install result:", result.returncode)

# Check again
result = subprocess.run("which pdftotext", shell=True, capture_output=True, text=True, timeout=10)
print("pdftotext:", result.stdout.strip() or "NOT FOUND")

if result.stdout.strip():
    # Extract text
    result = subprocess.run("pdftotext -layout /data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/uploads/崔亚飞.pdf -", shell=True, capture_output=True, text=True, timeout=30)
    print("=== 崔亚飞 ===")
    print(result.stdout[:8000])
