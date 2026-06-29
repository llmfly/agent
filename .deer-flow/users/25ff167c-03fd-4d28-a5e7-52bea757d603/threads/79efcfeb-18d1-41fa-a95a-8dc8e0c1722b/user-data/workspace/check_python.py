import subprocess
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')

# Try common locations
import os
python_bin = subprocess.run(['which', 'python3'], capture_output=True, text=True).stdout.strip()
print(f"python3: {python_bin}")

# Check what python3 maps to
r = subprocess.run(['python3', '-c', 'import sys; print(sys.executable); print(sys.path)'], capture_output=True, text=True)
print(r.stdout[:2000])
print(r.stderr[:2000])

# List installed packages related to pdf
r = subprocess.run(['python3', '-m', 'pip', 'list', '--format=columns'], capture_output=True, text=True)
print("PIP LIST:", r.stdout[:3000])
print("PIP ERR:", r.stderr[:500])
