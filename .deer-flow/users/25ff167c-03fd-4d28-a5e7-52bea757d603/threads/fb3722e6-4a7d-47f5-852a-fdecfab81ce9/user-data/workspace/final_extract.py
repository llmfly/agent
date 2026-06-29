import subprocess, sys

# Install PyMuPDF silently
subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF", "-q"], 
               capture_output=True, timeout=60)

import fitz

data = {}
for path, name in [("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/崔亚飞.pdf", "崔亚飞"),
                    ("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/杨佳文-java后端-v8.pdf", "杨佳文")]:
    doc = fitz.open(path)
    texts = [page.get_text() for page in doc]
    data[name] = "\n".join(texts)
    doc.close()

# Write combined output
import os
os.makedirs("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs", exist_ok=True)

with open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/extracted_text.txt", "w", encoding="utf-8") as f:
    for name in data:
        f.write(f"\n========== {name} ==========\n\n{data[name]}\n")

print("DONE:", {k: len(v) for k, v in data.items()})
print("---CUIYAFEI---")
print(data["崔亚飞"][:3000])
print("---YANGJIAWEN---")
print(data["杨佳文"][:3000])
