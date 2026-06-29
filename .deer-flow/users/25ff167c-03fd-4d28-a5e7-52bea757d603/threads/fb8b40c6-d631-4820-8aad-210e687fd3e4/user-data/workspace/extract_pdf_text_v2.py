#!/usr/bin/env python3
"""Try multiple PDF parsing approaches."""
import os
import re

# Check file
pdf_path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb8b40c6-d631-4820-8aad-210e687fd3e4/user-data/uploads/1201060226271-1Pys.pdf"
print(f"File exists: {os.path.exists(pdf_path)}")
print(f"Is file: {os.path.isfile(pdf_path)}")
print(f"Is link: {os.path.islink(pdf_path)}")
print(f"Real path: {os.path.realpath(pdf_path)}")
print(f"Size: {os.path.getsize(pdf_path)}")

# Read raw content
with open(pdf_path, "rb") as f:
    data = f.read()

print(f"\n--- First 200 bytes ---")
print(data[:200])

# Decode as latin-1 and look for text
text = data.decode('latin-1')

# Look for PDF text markers
print(f"\n--- Looking for Tj (text showing) operators ---")
tj_matches = re.findall(r'\((.*?)\)\s*Tj', text)
for m in tj_matches[:30]:
    m = m.replace('\\(', '(').replace('\\)', ')').replace('\\n', '\n')
    print(f"  Tj: '{m}'")

print(f"\n--- Looking for TJ (text array) operators ---")
tj_array = re.findall(r'\[(.*?)\]\s*TJ', text)
for arr in tj_array[:20]:
    parts = re.findall(r'\((.*?)\)', arr)
    line = ''.join(parts).replace('\\(', '(').replace('\\)', ')')
    if line.strip():
        print(f"  TJ: '{line}'")

print(f"\n--- Looking for hex strings ---")
hex_strs = re.findall(r'<([0-9A-Fa-f]+)>', text)
for h in hex_strs[:30]:
    try:
        # Try UTF-16BE (common in PDF for CJK)
        d = bytes.fromhex(h).decode('utf-16-be', errors='replace')
        if any(c.isalpha() for c in d):
            print(f"  Hex UTF-16BE: {h[:40]}... -> '{d[:60]}'")
    except:
        pass
    try:
        # Try raw bytes as text
        d = bytes.fromhex(h).decode('latin-1')
        if any(c.isalpha() for c in d) and len(d) > 3:
            print(f"  Hex Latin-1: {h[:40]}... -> '{d[:60]}'")
    except:
        pass
