#!/usr/bin/env python3
import subprocess, os

r = subprocess.run(["python3", "-m", "pip", "list", "--format=columns"], capture_output=True, text=True)
print(r.stdout[:500])
print("STDERR:", r.stderr[:200])
