#!/bin/bash
# Use python3 directly with inline script
python3 -c "
import subprocess, sys
# Try installing pymupdf quietly  
subprocess.run([sys.executable, '-m', 'pip', 'install', 'PyMuPDF'], capture_output=True, timeout=60)
import fitz
doc = fitz.open('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/2f424c6d-41c4-4383-9882-691f9a132244/user-data/uploads/杨佳文-java后端-v8.pdf')
print('Pages:', doc.page_count)
for i in range(doc.page_count):
    text = doc[i].get_text()
    print('=== Page', i+1, '===')
    print(text if text.strip() else '(no text)')
doc.close()
" 2>&1
