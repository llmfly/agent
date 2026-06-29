#!/usr/bin/env python3
import subprocess

# Run the check scripts
r1 = subprocess.run(["python3", "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/75b62093-6620-41ed-b3ce-70c2a69ad6ad/user-data/workspace/check_libs.py"], capture_output=True, text=True, timeout=30)
print("=== Available Python PDF libs ===")
print(r1.stdout)

r2 = subprocess.run(["python3", "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/75b62093-6620-41ed-b3ce-70c2a69ad6ad/user-data/workspace/check_system.py"], capture_output=True, text=True, timeout=120)
print("\n=== System check ===")
out = r2.stdout
# Show last 2000 chars
print(out[-2000:])
if r2.stderr:
    print("STDERR:", r2.stderr[:300])
