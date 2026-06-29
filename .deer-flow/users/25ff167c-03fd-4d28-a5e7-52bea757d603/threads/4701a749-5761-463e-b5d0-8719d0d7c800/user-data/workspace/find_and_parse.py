#!/usr/bin/env python3
"""Find the actual path of the PDF file and try to parse it."""
import os
import subprocess

# Search for the file
for root, dirs, files in os.walk("/mnt"):
    for f in files:
        if "2Pys" in f or "120106" in f:
            full_path = os.path.join(root, f)
            print(f"Found: {full_path}")
            print(f"Size: {os.path.getsize(full_path)}")
            print(f"Full realpath: {os.path.realpath(full_path)}")
            
            # Try to extract text
            try:
                result = subprocess.run(
                    ["python3", "-c", f"""
import fitz
try:
    doc = fitz.open("{full_path}")
    print(f"Pages: {{doc.page_count}}")
    for i, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            print(f"\\n=== Page {{i+1}} ===")
            print(text[:3000])
    doc.close()
except Exception as e:
    print(f"fitz error: {{e}}")

import pdfminer
except:
    pass
# Try basic text extraction from raw content
with open("{full_path}", "rb") as f:
    raw = f.read()
# Look for readable text
import re
# Try to decode as latin-1 to preserve all bytes
text = raw.decode('latin-1')
# Find sequences of alphanumeric/ASCII chars
words = re.findall(r'[\\x20-\\x7E]{{4,}}', text)
print(f"\\nFound {{len(words)}} ASCII word sequences")
for w in words[:30]:
    print(w)
"""],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                print("STDOUT:", result.stdout[:5000])
                if result.stderr:
                    print("STDERR:", result.stderr[:1000])
            except Exception as e:
                print(f"Run error: {e}")
