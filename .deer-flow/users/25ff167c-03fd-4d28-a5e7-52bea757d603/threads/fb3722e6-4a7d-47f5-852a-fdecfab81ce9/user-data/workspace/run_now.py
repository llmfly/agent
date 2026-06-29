# Direct inline extraction
import os, sys

os.makedirs("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs", exist_ok=True)

# First install PyMuPDF
import subprocess
r = subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF"], 
                   capture_output=True, text=True, timeout=60)
print("Install status:", r.returncode)
if r.returncode != 0:
    print("STDERR:", r.stderr[:500])
else:
    print("PyMuPDF installed successfully")

# Now import and extract
import fitz

for path, name in [
    ("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/崔亚飞.pdf", "崔亚飞"),
    ("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/杨佳文-java后端-v8.pdf", "杨佳文")
]:
    print(f"\nProcessing {name}...")
    doc = fitz.open(path)
    text = ""
    for i, page in enumerate(doc):
        t = page.get_text()
        if t.strip():
            text += t + "\n"
        print(f"  Page {i+1}: {len(t)} chars")
    doc.close()
    
    out = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/{name}.txt"
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Saved {len(text)} chars to {out}")
    
    # Print first 1000 chars
    print(f"  Preview: {text[:500]}...")

print("\nAll done!")
