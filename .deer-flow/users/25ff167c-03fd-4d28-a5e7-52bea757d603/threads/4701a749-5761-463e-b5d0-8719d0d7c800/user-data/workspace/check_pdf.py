#!/usr/bin/env python3
"""Try to extract content from the PDF file."""
import subprocess
import sys

result = subprocess.run(
    ["python3", "-c", """
import sys
# Try reading the PDF with built-in tools
with open('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/4701a749-5761-463e-b5d0-8719d0d7c800/user-data/uploads/1201060226271-2Pys.pdf', 'rb') as f:
    content = f.read()

# Check if it's a valid PDF
if content[:5] == b'%PDF-':
    print(f"Valid PDF detected. Size: {len(content)} bytes")
else:
    print(f"Not a standard PDF header: {content[:20]}")
    sys.exit(1)

# Try to find and extract plain text from the PDF
# PDFs often contain text in parentheses or between BT/ET markers
text = content.decode('latin-1')

# Extract text between parentheses (PDF text objects)
import re
# Find text between parentheses in PDF streams
texts = re.findall(r'\\([^)]*)\\)', text)
# Find Chinese characters
chinese = re.findall(r'[\u4e00-\u9fff]+', text)

print(f"Found {len(chinese)} Chinese text segments")
for c in chinese[:50]:
    print(c)

print(f"\\nFound {len(texts)} parenthesized text segments")
for t in texts[:50]:
    if len(t) > 2:
        print(t)
"""],
    capture_output=True,
    text=True
)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
