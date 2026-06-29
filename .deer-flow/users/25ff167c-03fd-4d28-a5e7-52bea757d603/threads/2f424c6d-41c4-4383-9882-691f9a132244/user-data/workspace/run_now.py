#!/usr/bin/env python3
import subprocess, sys
result = subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF"], capture_output=True, text=True, timeout=60)
print("Install:", result.returncode, result.stderr[:200])
result2 = subprocess.run([sys.executable, "-c", "import fitz; d=fitz.open('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/2f424c6d-41c4-4383-9882-691f9a132244/user-data/uploads/杨佳文-java后端-v8.pdf'); print(d.page_count); [print(f'===PAGE {i+1}==='); print(d[i].get_text() or '(empty)') for i in range(d.page_count)]"], capture_output=True, text=True, timeout=30)
print(result2.stdout[:5000])
print("ERR:", result2.stderr[:500])
