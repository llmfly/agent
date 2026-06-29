#!/usr/bin/env python3
# Check for available PDF tools
import subprocess, os, sys

# Check PATH
print("PATH:", os.environ.get("PATH", ""))

# Check common locations
for loc in ["/usr/bin", "/usr/local/bin", "/opt"]:
    for f in os.listdir(loc) if os.path.isdir(loc) else []:
        if "pdf" in f.lower() or "poppler" in f.lower():
            print(f"Found: {loc}/{f}")

# Check for poppler
r = subprocess.run(["dpkg", "-l", "poppler-utils"], capture_output=True, text=True)
print("\npoppler-utils:", r.stdout[-200:] if "ii" in r.stdout else "NOT INSTALLED")

# Check for any pdf-related binaries
r = subprocess.run("dpkg -l | grep -i pdf", shell=True, capture_output=True, text=True)
print("\nPDF packages:", r.stdout if r.stdout else "None")

# Try installing
print("\n--- Trying apt install ---")
r = subprocess.run("apt-get update 2>&1 | tail -1", shell=True, capture_output=True, text=True, timeout=60)
print("Update:", r.stdout, r.stderr[:100])
r = subprocess.run("apt-get install -y poppler-utils 2>&1 | tail -5", shell=True, capture_output=True, text=True, timeout=120)
print("Install:", r.stdout, r.stderr[:100])
