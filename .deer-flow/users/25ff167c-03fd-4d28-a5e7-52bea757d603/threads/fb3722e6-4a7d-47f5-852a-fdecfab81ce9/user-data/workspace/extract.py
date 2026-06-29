import sys, os, subprocess

# Install PyMuPDF
subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF", "-q"], capture_output=True, timeout=60)

import fitz

os.makedirs("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs", exist_ok=True)

for path, name in [
    ("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/崔亚飞.pdf", "崔亚飞"),
    ("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/杨佳文-java后端-v8.pdf", "杨佳文")
]:
    doc = fitz.open(path)
    lines = []
    for page in doc:
        t = page.get_text()
        if t.strip():
            lines.append(t)
    doc.close()
    full = "\n".join(lines)
    
    with open(f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/{name}.txt", "w", encoding="utf-8") as f:
        f.write(full)
    
    print(f"=== {name} ({len(full)} chars) ===")
    print(full)

print("\n✅ ALL DONE")
