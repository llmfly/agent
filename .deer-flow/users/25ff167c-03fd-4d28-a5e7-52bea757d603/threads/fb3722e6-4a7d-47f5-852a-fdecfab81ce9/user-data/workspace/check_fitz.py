import subprocess, sys
r = subprocess.run([sys.executable, "-c", "import fitz; print('ok')"], capture_output=True, text=True)
print("Fitz check:", r.stdout, r.stderr[:200])
if r.returncode != 0:
    r2 = subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF"], capture_output=True, text=True)
    print("Install:", r2.stdout[-200:], r2.stderr[:200])
