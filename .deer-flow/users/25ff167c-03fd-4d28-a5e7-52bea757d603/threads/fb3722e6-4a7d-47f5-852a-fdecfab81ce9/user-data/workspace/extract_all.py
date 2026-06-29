import subprocess, sys, os, json

# First install PyMuPDF
r1 = subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF"], 
                   capture_output=True, text=True, timeout=60)
print("PIP INSTALL:", r1.returncode)

# Now extract
import fitz

outpath = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/resume_text.txt"
os.makedirs("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs", exist_ok=True)

all_texts = {}

with open(outpath, "w", encoding="utf-8") as f:
    for path, name in [("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/崔亚飞.pdf", "崔亚飞"),
                        ("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/杨佳文-java后端-v8.pdf", "杨佳文")]:
        doc = fitz.open(path)
        texts = []
        f.write(f"\n{'='*80}\n=== {name} ===\n{'='*80}\n\n")
        for page in doc:
            t = page.get_text()
            if t.strip():
                f.write(t + "\n\n")
                texts.append(t)
        doc.close()
        all_texts[name] = "\n".join(texts)

# Also save to workspace
with open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/workspace/resume_text.txt", "w", encoding="utf-8") as f:
    for name, txt in all_texts.items():
        f.write(f"\n{'='*80}\n=== {name} ===\n{'='*80}\n\n{txt}\n")

print(f"Done! Extracted texts saved.")
for name, txt in all_texts.items():
    print(f"\n{'='*60}")
    print(f"=== {name} ({len(txt)} chars) ===")
    print(f"{'='*60}")
    print(txt[:2000])
    print(f"\n... [truncated, total {len(txt)} chars]")
