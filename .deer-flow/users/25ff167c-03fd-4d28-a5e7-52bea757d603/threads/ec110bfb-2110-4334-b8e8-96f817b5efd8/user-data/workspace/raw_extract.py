import re, sys

# Read raw PDF bytes and extract text between parentheses (PDF text objects)
with open('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/ec110bfb-2110-4334-b8e8-96f817b5efd8/user-data/uploads/崔亚飞.pdf', 'rb') as f:
    data = f.read()

# Try to decode as latin-1 and find text patterns
text = data.decode('latin-1')

# Find text between parentheses in PDF
matches = re.findall(r'\(([^)]*)\)', text)
for m in matches:
    # Filter out gibberish (binary data encoded as latin-1)
    clean = ''.join(c if c.isprintable() or c in ' \n\t' else '?' for c in m)
    if len(clean) > 3 and not all(c in '\\/ \n\t' for c in clean):
        print(clean[:200])
