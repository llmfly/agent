#!/usr/bin/env python3
"""Extract text from PDF using only standard library + available tools."""
import os
import re
import sys

pdf_path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/2f424c6d-41c4-4383-9882-691f9a132244/user-data/uploads/杨佳文-java后端-v8.pdf"

# Method 1: Try to use pdftotext if available
import subprocess
try:
    result = subprocess.run(["pdftotext", pdf_path, "-"], 
                          capture_output=True, text=True, timeout=30)
    if result.returncode == 0 and result.stdout.strip():
        print(result.stdout)
        sys.exit(0)
except:
    pass

# Method 2: Manual extraction from PDF binary
with open(pdf_path, "rb") as f:
    data = f.read()

# Try UTF-16 (common for CJK PDFs)
# Look for BOM
if data[:2] == b'\xff\xfe':
    try:
        text = data.decode('utf-16-le')
        print(text[:5000])
        sys.exit(0)
    except:
        pass

# Extract text between parentheses (PDF text objects)
def extract_pdf_text(data):
    """Extract text from PDF binary content."""
    texts = []
    i = 0
    while i < len(data):
        # Look for parenthesized strings
        if data[i:i+1] == b'(':
            depth = 1
            j = i + 1
            while j < len(data) and depth > 0:
                if data[j:j+1] == b'\\':
                    j += 2  # skip escaped char
                    continue
                if data[j:j+1] == b'(':
                    depth += 1
                elif data[j:j+1] == b')':
                    depth -= 1
                j += 1
            raw = data[i+1:j-1]
            # Try various decodings
            for enc in ['utf-8', 'latin-1', 'gbk', 'gb2312', 'utf-16-be', 'big5']:
                try:
                    t = raw.decode(enc)
                    if any('\u4e00' <= c <= '\u9fff' for c in t) or len(t) > 5:
                        texts.append(t)
                        break
                except:
                    continue
            i = j
        else:
            i += 1
    
    return texts

texts = extract_pdf_text(data)
print("\n".join(texts[:200]))

# Also try to find text in PDF streams
# Look for hex strings <...>
hex_texts = []
for m in re.finditer(rb'<([0-9A-Fa-f]+)>', data):
    hex_str = m.group(1).decode('ascii')
    try:
        decoded = bytes.fromhex(hex_str).decode('utf-16-be')
        if any('\u4e00' <= c <= '\u9fff' for c in decoded):
            hex_texts.append(decoded)
    except:
        pass

print("\n=== Hex decoded text ===")
for t in hex_texts[:100]:
    print(t)
