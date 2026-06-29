#!/usr/bin/env python3
import subprocess, os, sys, re

os.chdir('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace')

with open('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/uploads/崔亚飞.pdf', 'rb') as f:
    data = f.read()

print(f"File size: {len(data)} bytes")

# Find all readable strings
text = data.decode('latin-1')
# Find text between parentheses (PDF convention)
matches = re.findall(r'\(([^)]{3,})\)', text)
output = []
for m in matches:
    # Filter out non-readable PDF operators
    if not m.startswith('\\'):
        # Decode PDF escape sequences
        cleaned = m.replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t')
        output.append(cleaned)

print("=== Extracted text objects ===")
for line in output[:300]:
    print(line)
