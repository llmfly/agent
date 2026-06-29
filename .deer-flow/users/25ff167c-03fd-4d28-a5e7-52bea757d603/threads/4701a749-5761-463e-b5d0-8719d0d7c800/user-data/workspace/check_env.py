import subprocess
result = subprocess.run(["ls", "-la", "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/4701a749-5761-463e-b5d0-8719d0d7c800/user-data/uploads/1201060226271-2Pys.pdf"], capture_output=True, text=True)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
# Also try stat
result2 = subprocess.run(["stat", "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/4701a749-5761-463e-b5d0-8719d0d7c800/user-data/uploads/1201060226271-2Pys.pdf"], capture_output=True, text=True)
print("STAT STDOUT:", result2.stdout)
print("STAT STDERR:", result2.stderr)
# Check what Python modules are available
result3 = subprocess.run(["python3", "-c", "import sys; print(sys.version); import pkg_resources; pkgs = [d for d in pkg_resources.working_set]; print([p.key for p in pkgs if 'pdf' in p.key or 'docx' in p.key or 'fitz' in p.key or 'mine' in p.key])"], capture_output=True, text=True)
print("PYTHON:", result3.stdout, result3.stderr)
