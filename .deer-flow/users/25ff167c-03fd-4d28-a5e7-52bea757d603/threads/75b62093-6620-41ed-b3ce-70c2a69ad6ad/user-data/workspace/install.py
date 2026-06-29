#!/usr/bin/env python3
import subprocess

r = subprocess.run("apt-get update -qq && apt-get install -y -qq poppler-utils 2>&1", shell=True, capture_output=True, text=True, timeout=120)
print("STDOUT:", r.stdout[-300:])
print("STDERR:", r.stderr[-300:])
print("Return:", r.returncode)

# Check if installed
r2 = subprocess.run(["which", "pdftotext"], capture_output=True, text=True)
print("pdftotext at:", r2.stdout, r2.stderr)
