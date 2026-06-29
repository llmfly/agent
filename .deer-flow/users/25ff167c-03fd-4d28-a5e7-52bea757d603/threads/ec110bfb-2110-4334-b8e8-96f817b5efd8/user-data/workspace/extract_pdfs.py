import subprocess
import sys
import os

# Check if already installed
try:
    from pdfminer.high_level import extract_text
    print("pdfminer already available")
except ImportError:
    result = subprocess.run([sys.executable, "-m", "pip", "install", "pdfminer.six", "-q"], capture_output=True, text=True)
    print("Install result:", result.returncode, result.stderr[:200] if result.stderr else "ok")
    from pdfminer.high_level import extract_text

file1 = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/ec110bfb-2110-4334-b8e8-96f817b5efd8/user-data/uploads/崔亚飞.pdf"
file2 = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/ec110bfb-2110-4334-b8e8-96f817b5efd8/user-data/uploads/杨佳文-java后端-v8.pdf"

for fname, label in [(file1, "FILE 1: 崔亚飞.pdf"), (file2, "FILE 2: 杨佳文-java后端-v8.pdf")]:
    if not os.path.exists(fname):
        print(f"File not found: {fname}")
        continue
    print("=" * 80)
    print(label)
    print("=" * 80)
    try:
        text = extract_text(fname)
        out_path = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/ec110bfb-2110-4334-b8e8-96f817b5efd8/user-data/workspace/{os.path.splitext(os.path.basename(fname))[0]}.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Extracted {len(text)} chars, saved to {out_path}")
        print("---CONTENT START---")
        print(text[:5000])
        if len(text) > 5000:
            print(f"\n... [total {len(text)} chars]")
        print("---CONTENT END---")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
