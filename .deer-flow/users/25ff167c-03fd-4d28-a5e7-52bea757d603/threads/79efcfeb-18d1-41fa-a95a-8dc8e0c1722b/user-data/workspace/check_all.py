#!/usr/bin/env python3
import os, sys, subprocess

os.chdir('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace')

# Check
r = subprocess.run(['which', 'pdftotext'], capture_output=True, text=True)
print("pdftotext:", r.stdout.strip() or "NOT FOUND")

r = subprocess.run(['python3', '-c', 'import sys; print(sys.executable)'], capture_output=True, text=True)
print("python:", r.stdout.strip())

# Try extracting text using strings command as fallback
r = subprocess.run(['strings', '/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/uploads/崔亚飞.pdf'], capture_output=True, text=True, timeout=10)
print("\n=== 崔亚飞.pdf (strings) ===")
print(r.stdout[:3000])
