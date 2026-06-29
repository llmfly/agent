#!/usr/bin/env python3
import sys
# Check if pymupdf can be directly used
try:
    import fitz
    doc = fitz.open('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/2f424c6d-41c4-4383-9882-691f9a132244/user-data/uploads/杨佳文-java后端-v8.pdf')
    for i in range(doc.page_count):
        print(f'=== PAGE {i+1} ===')
        print(doc[i].get_text())
    doc.close()
except ImportError:
    print("NEED_INSTALL")
except Exception as e:
    print(f"ERROR: {e}")
