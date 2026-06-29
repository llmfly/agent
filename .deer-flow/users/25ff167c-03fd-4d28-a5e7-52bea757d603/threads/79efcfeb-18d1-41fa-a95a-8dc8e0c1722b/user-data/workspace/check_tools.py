import subprocess
import os

# Check what tools are available
for cmd in ['pdftotext', 'pdftotext', 'python3']:
    r = subprocess.run(['which', cmd], capture_output=True, text=True)
    print(f"{cmd}: {r.stdout.strip() or 'not found'}")

# Check python version
r = subprocess.run(['python3', '--version'], capture_output=True, text=True)
print(f"Python: {r.stdout.strip()}")

# Check if pip can list packages
r = subprocess.run(['python3', '-m', 'pip', 'list', '--format=columns'], capture_output=True, text=True)
print(r.stdout[:2000])
print(r.stderr[:2000])
