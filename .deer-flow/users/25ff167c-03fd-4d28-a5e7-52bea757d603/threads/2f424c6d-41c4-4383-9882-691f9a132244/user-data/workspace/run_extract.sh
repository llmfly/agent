#!/bin/bash
cd /data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/2f424c6d-41c4-4383-9882-691f9a132244/user-data/workspace
pip3 install PyMuPDF 2>&1 | tail -3
echo "---"
python3 -c "
import fitz
doc = fitz.open('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/2f424c6d-41c4-4383-9882-691f9a132244/user-data/uploads/杨佳文-java后端-v8.pdf')
print('Pages:', doc.page_count)
for i in range(doc.page_count):
    text = doc[i].get_text()
    print('=== PAGE', i+1, '===')
    print(text if text.strip() else '(empty)')
doc.close()
" 2>&1
