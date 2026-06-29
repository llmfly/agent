#!/usr/bin/env python3
import subprocess, os

print("=== Python version ===")
r = subprocess.run(["python3", "--version"], capture_output=True, text=True)
print(r.stdout)

print("\n=== check_python ===")
r = subprocess.run(["python3", "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/75b62093-6620-41ed-b3ce-70c2a69ad6ad/user-data/workspace/check_libs.py"], capture_output=True, text=True, timeout=30)
print(r.stdout)
print(r.stderr[:200] if r.stderr else "")

print("\n=== check_system ===")
r = subprocess.run(["python3", "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/75b62093-6620-41ed-b3ce-70c2a69ad6ad/user-data/workspace/check_system.py"], capture_output=True, text=True, timeout=120)
print(r.stdout[-2000:])
print(r.stderr[:200] if r.stderr else "")
