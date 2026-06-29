# Try using only stdlib - no PyMuPDF needed
import os, sys, re

# PDF text extraction without external libraries
# This extracts text from simple PDFs using basic regex on raw bytes

def extract_text_simple(pdf_path):
    """Extract text from a PDF using simple parsing of raw bytes"""
    with open(pdf_path, "rb") as f:
        data = f.read()
    
    # Try to decode as latin-1 (PDFs often use this)
    text = data.decode("latin-1", errors="replace")
    
    # Extract text between parentheses in PDF
    # PDF text objects are often between parentheses: (text)
    texts = re.findall(r'\(([^)]*)\)', text)
    
    # Also look for BT...ET (Begin Text / End Text) blocks
    bt_blocks = re.findall(r'BT\s*(.*?)\s*ET', text, re.DOTALL)
    
    result = []
    for t in texts:
        # Filter out garbage
        if len(t) > 2 and all(ord(c) < 128 or ord(c) > 255 for c in t):
            cleaned = re.sub(r'\\[0-9]{3}', '', t)  # Remove octal escapes
            if cleaned.strip():
                result.append(cleaned)
    
    return "\n".join(result)

for path, name in [("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/崔亚飞.pdf", "崔亚飞"),
                    ("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/杨佳文-java后端-v8.pdf", "杨佳文")]:
    extracted = extract_text_simple(path)
    print(f"=== {name} ({len(extracted)} chars) ===")
    print(extracted[:2000])
    print()
