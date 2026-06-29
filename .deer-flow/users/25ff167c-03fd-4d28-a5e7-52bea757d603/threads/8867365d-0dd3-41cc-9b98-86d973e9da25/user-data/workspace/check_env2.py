import subprocess, sys

# Make script executable
# Check what's available
cmds = ["which pdftotext", "which pdftotext", "dpkg -l | grep -i poppler", "apt list --installed 2>/dev/null | grep -i pdf"]
for cmd in cmds:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
    out = (r.stdout + r.stderr)[:200]
    if out.strip():
        print(f"$ {cmd}")
        print(out[:200])
