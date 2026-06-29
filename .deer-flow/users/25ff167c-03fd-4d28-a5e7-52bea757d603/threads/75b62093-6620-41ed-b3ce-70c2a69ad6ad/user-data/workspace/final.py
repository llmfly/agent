#!/usr/bin/env python3
import subprocess

# Run the process  
r = subprocess.run(["python3", "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/75b62093-6620-41ed-b3ce-70c2a69ad6ad/user-data/workspace/runner.py"], capture_output=True, text=True, timeout=180)
print("STDOUT:")
print(r.stdout)
if r.stderr:
    print("\nSTDERR:")
    print(r.stderr[:500])
