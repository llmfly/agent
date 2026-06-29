#!/usr/bin/env python3
import subprocess
import sys
import os

file1 = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/ec110bfb-2110-4334-b8e8-96f817b5efd8/user-data/uploads/崔亚飞.pdf"
file2 = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/ec110bfb-2110-4334-b8e8-96f817b5efd8/user-data/uploads/杨佳文-java后端-v8.pdf"

for fname in [file1, file2]:
    print(f"File exists: {os.path.exists(fname)}, size: {os.path.getsize(fname) if os.path.exists(fname) else 'N/A'}")
