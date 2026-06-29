import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')

# Try pdftotext
import subprocess
r = subprocess.run(["pdftotext", "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf", "-"], capture_output=True, text=True, timeout=10)
print("pdftotext exit code:", r.returncode)
print("stdout:", r.stdout[:2000])
print("stderr:", r.stderr[:500])
