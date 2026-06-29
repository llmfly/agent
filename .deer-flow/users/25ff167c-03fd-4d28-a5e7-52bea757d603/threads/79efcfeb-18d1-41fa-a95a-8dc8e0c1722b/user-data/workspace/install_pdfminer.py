import subprocess, os

os.chdir('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace')

# Step by step
r = subprocess.run("pip3 install pdfminer.six", shell=True, capture_output=True, text=True, timeout=120)
print("INSTALL STDOUT:", r.stdout[-500:])
print("INSTALL STDERR:", r.stderr[-500:])
print("INSTALL RC:", r.returncode)
