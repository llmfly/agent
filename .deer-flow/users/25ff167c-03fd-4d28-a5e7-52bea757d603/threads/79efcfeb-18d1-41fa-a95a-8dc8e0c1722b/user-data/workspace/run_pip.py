import subprocess, os

os.chdir('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace')

r = subprocess.run("python3 /data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace/pip_extract.py", shell=True, capture_output=True, text=True, timeout=120)
print(r.stdout[:10000])
print(r.stderr[:1000])
print("RC:", r.returncode)
