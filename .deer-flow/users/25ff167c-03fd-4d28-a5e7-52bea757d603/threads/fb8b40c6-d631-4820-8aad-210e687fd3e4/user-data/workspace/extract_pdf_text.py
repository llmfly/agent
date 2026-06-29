#!/usr/bin/env python3
"""Read PDF file and extract text."""

# Read the file as raw bytes
with open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb8b40c6-d631-4820-8aad-210e687fd3e4/user-data/uploads/1201060226271-1Pys.pdf", "rb") as f:
    data = f.read()

# Print file info
print(f"File size: {len(data)} bytes")
print(f"First 50 bytes (hex): {data[:50].hex()}")
print(f"First 50 bytes (repr): {data[:50]}")

# Search for PDF text objects - between parentheses in PDF
content_str = data.decode('latin-1')

# Find all text objects in PDF
import re
texts = re.findall(r'\((.*?)\)', content_str)
print(f"\nFound {len(texts)} text segments in parentheses:")
for t in texts[:100]:
    t = t.replace('\\(', '(').replace('\\)', ')')
    if len(t) > 2 and not all(c in '\\/*-+ \t\n\r' for c in t):
        print(f"  '{t}'")

# Also try to find Unicode text (hex encoded)
print("\n\n=== Looking for hex-encoded text ===")
hex_texts = re.findall(r'<([0-9A-Fa-f]+)>', content_str)
for h in hex_texts[:50]:
    try:
        decoded = bytes.fromhex(h).decode('utf-16-be', errors='ignore')
        if any('\u4e00' <= c <= '\u9fff' for c in decoded):
            print(f"  Hex: {h} -> '{decoded}'")
    except:
        pass
