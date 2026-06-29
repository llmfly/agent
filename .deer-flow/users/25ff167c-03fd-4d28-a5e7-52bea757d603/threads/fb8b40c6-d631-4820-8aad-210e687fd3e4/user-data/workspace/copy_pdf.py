#!/usr/bin/env python3
"""Copy PDF from uploads to a simpler path and then parse it."""
import shutil, os

# First just copy
src = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb8b40c6-d631-4820-8aad-210e687fd3e4/user-data/uploads/1201060226271-1Pys.pdf"
dst = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb8b40c6-d631-4820-8aad-210e687fd3e4/user-data/workspace/doc.pdf"

if os.path.exists(src):
    shutil.copy2(src, dst)
    print(f"Copied to {dst}")
    print(f"Size: {os.path.getsize(dst)}")
else:
    # Try listing directory
    for f in os.listdir("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb8b40c6-d631-4820-8aad-210e687fd3e4/user-data/uploads"):
        print(f"  Found: {f} (repr: {repr(f)})")
    print("File not found!")
