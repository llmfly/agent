#!/usr/bin/env python3
import subprocess, os

files = ["杨佳文-java后端-v8.pdf", "崔亚飞.pdf"]
base_dir = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/7a337e80-4472-46f6-842e-b8b07fd387f6/user-data/uploads"
out_dir = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/7a337e80-4472-46f6-842e-b8b07fd387f6/user-data/workspace"

for f in files:
    infile = os.path.join(base_dir, f)
    outfile = os.path.join(out_dir, f + ".txt")
    r = subprocess.run(["pdftotext", "-layout", infile, outfile], capture_output=True, text=True, timeout=30)
    print(f"{f}: rc={r.returncode}")
    if os.path.exists(outfile):
        with open(outfile, 'r') as fh:
            content = fh.read()
        print(f"  Length: {len(content)} chars")
        print(f"  Start: {content[:300]}")
