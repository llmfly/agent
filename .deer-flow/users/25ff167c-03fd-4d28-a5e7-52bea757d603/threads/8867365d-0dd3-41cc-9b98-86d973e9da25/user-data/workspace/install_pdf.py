import subprocess, os, sys

# Use subprocess to run shell commands via exec
result = subprocess.run(["bash", "-c", "command -v pdftotext"], capture_output=True, text=True)
print("pdftotext:", result.stdout.strip() or "NOT FOUND")

result = subprocess.run(["bash", "-c", "command -v pdftotext"], capture_output=True, text=True)
print("pdftotext:", result.stdout.strip() or "NOT FOUND")

# Try to install pdftotext if not available
if not result.stdout.strip():
    print("Attempting to install poppler-utils...")
    result = subprocess.run(["bash", "-c", "apt-get update -qq && apt-get install -y -qq poppler-utils 2>&1 | tail -5"], capture_output=True, text=True, timeout=60)
    print(result.stdout)
    print(result.stderr)
