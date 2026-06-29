import sys, os, subprocess

# The problem is this script needs to be exec'd, not run as a subprocess
# Let's just run the extraction right here

# Install PyMuPDF
subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF", "-q"], capture_output=True, timeout=60)

import fitz

os.makedirs("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs", exist_ok=True)

results = {}
for path, name in [
    ("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/崔亚飞.pdf", "崔亚飞"),
    ("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/杨佳文-java后端-v8.pdf", "杨佳文")
]:
    doc = fitz.open(path)
    text = ""
    for page in doc:
        t = page.get_text()
        if t.strip():
            text += t + "\n"
    doc.close()
    results[name] = text
    
    out = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/{name}.txt"
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)

# Now print results
for name, text in results.items():
    print(f"\n{'='*60}")
    print(f"=== {name} ({len(text)} chars) ===")
    print(f"{'='*60}")
    print(text)

print("\n✅ All done!")
