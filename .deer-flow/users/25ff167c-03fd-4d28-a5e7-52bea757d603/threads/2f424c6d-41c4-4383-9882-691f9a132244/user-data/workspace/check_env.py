#!/usr/bin/env python3
import subprocess, sys

# Check what pip is available
r = subprocess.run(["which", "pip"], capture_output=True, text=True)
print(f"which pip: {r.stdout.strip()} or {r.stderr.strip()}")

r2 = subprocess.run(["which", "pip3"], capture_output=True, text=True)
print(f"which pip3: {r2.stdout.strip()} or {r2.stderr.strip()}")

# Check what python is
r3 = subprocess.run(["which", "python3"], capture_output=True, text=True)
print(f"which python3: {r3.stdout.strip() or r3.stderr.strip()}")

# Try pip3
r4 = subprocess.run(["pip3", "list", "--format=columns"], capture_output=True, text=True)
print(f"\npip3 list output:")
print(r4.stdout[:2000])
if r4.stderr:
    print(f"STDERR: {r4.stderr[:500]}")

# Try pip
r5 = subprocess.run(["pip", "list", "--format=columns"], capture_output=True, text=True)
print(f"\npip list output:")
print(r5.stdout[:2000])
if r5.stderr:
    print(f"STDERR: {r5.stderr[:500]}")
