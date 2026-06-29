import subprocess
result = subprocess.run(['python3', '/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace/check_tools.py'], capture_output=True, text=True, timeout=30)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
