import subprocess, sys, os

# Try with python3 directly
result = subprocess.run(["python3", "-m", "pip", "install", "pymupdf"], capture_output=True, text=True)
print("STDOUT:", result.stdout[-500:])
print("STDERR:", result.stderr[-500:])
print("Return:", result.returncode)

result2 = subprocess.run(["python3", "-c", "import fitz; print('OK')"], capture_output=True, text=True)
print("Import test out:", result2.stdout)
print("Import test err:", result2.stderr)
