import subprocess, sys

# Simple approach: use subprocess to run python
code = '''
import fitz
doc = fitz.open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/ec110bfb-2110-4334-b8e8-96f817b5efd8/user-data/uploads/崔亚飞.pdf")
text = ""
for page in doc:
    text += page.get_text()
print(text[:3000])
doc.close()
'''

# First install
subprocess.run([sys.executable, "-m", "pip", "install", "pymupdf"], capture_output=True)

r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
print("Out:", r.stdout[:2000])
print("Err:", r.stderr[:500])
