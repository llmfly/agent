"""Execute PDF extraction inline"""

# Step 1: Install PyMuPDF
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF"], 
               capture_output=True, text=True, timeout=60)

# Step 2: Extract
import fitz, os

os.makedirs("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs", exist_ok=True)

results = {}
for path, name in [("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/崔亚飞.pdf", "崔亚飞"),
                    ("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/杨佳文-java后端-v8.pdf", "杨佳文")]:
    doc = fitz.open(path)
    text_parts = []
    for page in doc:
        t = page.get_text()
        if t.strip():
            text_parts.append(t)
    doc.close()
    
    full_text = "\n".join(text_parts)
    results[name] = full_text
    
    out = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/{name}.txt"
    with open(out, "w", encoding="utf-8") as f:
        f.write(full_text)

# Step 3: Write a log to workspace
log_path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/workspace/extraction_log.txt"
with open(log_path, "w", encoding="utf-8") as f:
    for name, text in results.items():
        f.write(f"\n{'='*60}\n=== {name} ===\n{'='*60}\n")
        f.write(text[:10000])  # Write up to 10k chars
        if len(text) > 10000:
            f.write(f"\n\n... [truncated, total {len(text)} chars]\n")

print(f"Log written to {log_path}")
for name, text in results.items():
    print(f"{name}: {len(text)} chars")
