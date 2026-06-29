#!/usr/bin/env python3
import os
print(f"CWD: {os.getcwd()}")
print(f"User: {os.environ.get('USER', 'unknown')}")
print(f"Home: {os.environ.get('HOME', 'unknown')}")
print(f"PATH: {os.environ.get('PATH', 'unknown')[:200]}")
print(f"\nListing uploads:")
for f in os.listdir("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb8b40c6-d631-4820-8aad-210e687fd3e4/user-data/uploads"):
    print(f"  {repr(f)} - exists: {os.path.isfile(os.path.join('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb8b40c6-d631-4820-8aad-210e687fd3e4/user-data/uploads', f))}")
print(f"\nPWD content:")
for f in os.listdir("."):
    print(f"  {repr(f)}")
