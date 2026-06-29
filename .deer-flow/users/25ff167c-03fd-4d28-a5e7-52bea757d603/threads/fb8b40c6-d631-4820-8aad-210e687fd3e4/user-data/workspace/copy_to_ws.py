import shutil
import os

# Copy the file from uploads to workspace
src = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb8b40c6-d631-4820-8aad-210e687fd3e4/user-data/uploads/1201060226271-1Pys.pdf"
dst = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb8b40c6-d631-4820-8aad-210e687fd3e4/user-data/workspace/copied_doc.pdf"

if os.path.exists(src):
    shutil.copy2(src, dst)
    print(f"SUCCESS: Copied to {dst}")
    print(f"Size: {os.path.getsize(dst)} bytes")
else:
    print(f"FAILED: Source {src} does not exist")
