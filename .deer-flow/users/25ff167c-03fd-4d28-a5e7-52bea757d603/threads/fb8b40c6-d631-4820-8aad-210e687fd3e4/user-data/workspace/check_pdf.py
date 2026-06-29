import os
import subprocess

pdf_path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb8b40c6-d631-4820-8aad-210e687fd3e4/user-data/uploads/1201060226271-1Pys.pdf"

print(f"File exists: {os.path.exists(pdf_path)}")
print(f"Is symlink: {os.path.islink(pdf_path)}")
print(f"Real path: {os.path.realpath(pdf_path)}")
print(f"File size: {os.path.getsize(pdf_path)}")

# Try reading first 100 bytes
with open(pdf_path, 'rb') as f:
    header = f.read(100)
print(f"Header (hex): {header[:20].hex()}")
print(f"Header (repr): {repr(header[:50])}")

# Check if it's actually a PDF
if header[:5] == b'%PDF-':
    print("✓ Valid PDF header detected")
else:
    print("✗ NOT a PDF file")

# Try using pdftotext
result = subprocess.run(["which", "pdftotext"], capture_output=True, text=True)
print(f"\npdftotext available: {result.stdout}")

# Try using python pdfminer
try:
    from pdfminer.high_level import extract_text
    print("pdfminer available")
except:
    print("pdfminer not available")
