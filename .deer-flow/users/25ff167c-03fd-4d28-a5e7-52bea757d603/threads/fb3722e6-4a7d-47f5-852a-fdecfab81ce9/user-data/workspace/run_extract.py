# This script installs PyMuPDF, extracts text from both PDFs, and saves to output
import subprocess, sys, os

# Step 1: Try to import fitz, install if needed
try:
    import fitz
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyMuPDF", "-q"])
    import fitz

# Step 2: Extract text
output_path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs/resume_text.txt"
os.makedirs("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/outputs", exist_ok=True)

with open(output_path, "w", encoding="utf-8") as f:
    for path, name in [("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/崔亚飞.pdf", "崔亚飞"),
                        ("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/uploads/杨佳文-java后端-v8.pdf", "杨佳文")]:
        doc = fitz.open(path)
        f.write(f"\n{'='*80}\n=== {name} ===\n{'='*80}\n\n")
        for page in doc:
            t = page.get_text()
            if t.strip():
                f.write(t + "\n\n")
        doc.close()

print(f"Done! File saved. Size: {os.path.getsize(output_path)} bytes")
