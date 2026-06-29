# Quick pdftotext test
import subprocess
r = subprocess.run(["which", "pdftotext"], capture_output=True, text=True, timeout=5)
print("which:", r.stdout, r.stderr, r.returncode)

r = subprocess.run(["pdftotext", "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/1a0822b1-d831-4091-84c0-66f524443ef4/user-data/uploads/杨佳文-java后端-v8.pdf", "-"], capture_output=True, text=True, timeout=10)
print("rc:", r.returncode)
print("out:", repr(r.stdout[:500]))
print("err:", repr(r.stderr[:500]))
