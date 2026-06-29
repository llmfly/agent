import sys
print(f"Python: {sys.version}")
r = subprocess.run(["which", "pdftotext"], capture_output=True, text=True)
print(f"pdftotext: {r.stdout.strip() or 'NOT FOUND'}")
r = subprocess.run(["which", "pdftotext"], capture_output=True, text=True)
print(f"pdftotext: {r.stdout.strip() or 'NOT FOUND'}")
import os
os.system("ls /usr/bin/pdftotext /usr/local/bin/pdftotext 2>/dev/null || echo 'pdftotext not found in standard bins'")
os.system("ls /usr/bin/python* /usr/local/bin/python* 2>/dev/null | head -5")
os.system("apt list --installed 2>/dev/null | grep -i pdf | head -5")
