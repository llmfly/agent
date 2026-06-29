#!/usr/bin/env python3
"""Run extraction and save results to a readable text file"""
import subprocess, sys, os

# First check if fitz is available
try:
    import fitz
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF", "-q"], 
                   capture_output=True, timeout=60)
    import fitz

output = {}

for path, name in [("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/崔亚飞.pdf", "崔亚飞"), 
                    ("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/杨佳文-java后端-v8.pdf", "杨佳文")]:
    doc = fitz.open(path)
    pages_text = []
    for page in doc:
        t = page.get_text()
        if t.strip():
            pages_text.append(t)
    output[name] = "\n\n".join(pages_text)
    doc.close()

# Write to workspace
result_path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/workspace/resume_text.txt"
with open(result_path, "w", encoding="utf-8") as f:
    for name in output:
        f.write(f"\n{'='*80}\n=== {name} ===\n{'='*80}\n\n")
        f.write(output[name])
        f.write("\n")

# Also copy to outputs
out_path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/resume_text.txt"
os.makedirs("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs", exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    for name in output:
        f.write(f"\n{'='*80}\n=== {name} ===\n{'='*80}\n\n")
        f.write(output[name])
        f.write("\n")

print("Done! Text saved to:", result_path)
print("Also saved to:", out_path)
print(f"\nCharacters extracted: {sum(len(v) for v in output.values())}")
