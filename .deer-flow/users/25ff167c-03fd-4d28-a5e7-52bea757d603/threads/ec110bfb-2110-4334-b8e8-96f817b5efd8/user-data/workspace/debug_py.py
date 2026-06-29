import subprocess, sys

# Check what python version we have
r = subprocess.run(["python3", "--version"], capture_output=True, text=True)
print("python3:", r.stdout, r.stderr, file=sys.stderr)

# Try pip install
r = subprocess.run(["python3", "-m", "pip", "install", "pdfminer.six"], capture_output=True, text=True)
print("pip out:", r.stdout[-300:], file=sys.stderr)
print("pip err:", r.stderr[-300:], file=sys.stderr)
print("return:", r.returncode, file=sys.stderr)

# Try import
r = subprocess.run(["python3", "-c", "from pdfminer.high_level import extract_text; print('ok')"], capture_output=True, text=True)
print("import out:", r.stdout, file=sys.stderr)
print("import err:", r.stderr, file=sys.stderr)
