#!/usr/bin/env python3
# This version actually installs and extracts
import subprocess, os, sys

print("Step 1: Update apt", flush=True)
r = subprocess.run(["apt-get", "update", "-qq"], capture_output=True, text=True, timeout=60)
print(f"  return={r.returncode}, err={r.stderr[:100]}")

print("Step 2: Install poppler", flush=True)
r = subprocess.run(["apt-get", "install", "-y", "-qq", "poppler-utils"], capture_output=True, text=True, timeout=120)
print(f"  return={r.returncode}, err={r.stderr[:100]}")

print("Step 3: Check pdftotext", flush=True)
r = subprocess.run(["which", "pdftotext"], capture_output=True, text=True)
print(f"  result: {r.stdout}{r.stderr}")

print("Step 4: Check dpkg", flush=True)
r = subprocess.run(["dpkg", "-l", "poppler-utils"], capture_output=True, text=True)
print(f"  {r.stdout[:200]}")

print("Step 5: Try pdftotext on first file", flush=True)
path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/75b62093-6620-41ed-b3ce-70c2a69ad6ad/user-data/uploads/崔亚飞.pdf"
r = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, timeout=30)
print(f"  return={r.returncode}, stdout_len={len(r.stdout)}, err={r.stderr[:200]}")

if r.stdout.strip():
    print("\n=== CONTENT (first 3000 chars) ===")
    print(r.stdout[:3000])
else:
    # Try with direct path
    r2 = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True, timeout=30)
    print(f"  (no layout) return={r2.returncode}, stdout_len={len(r2.stdout)}, err={r2.stderr[:200]}")

print("\nStep 6: Try PyMuPDF instead", flush=True)
try:
    import fitz
    print("  PyMuPDF available!")
    doc = fitz.open(path)
    print(f"  Pages: {len(doc)}")
    for page in doc:
        print(f"\n--- Page {page.number + 1} ---")
        print(page.get_text())
except ImportError:
    print("  PyMuPDF not available, trying to install...")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF", "-q"], capture_output=True, text=True, timeout=60)
    print(f"  Install result: {r.returncode}")
    try:
        import fitz
        print("  Now available!")
        doc = fitz.open(path)
        print(f"  Pages: {len(doc)}")
        for page in doc:
            print(page.get_text())
    except Exception as e:
        print(f"  Still failed: {e}")
