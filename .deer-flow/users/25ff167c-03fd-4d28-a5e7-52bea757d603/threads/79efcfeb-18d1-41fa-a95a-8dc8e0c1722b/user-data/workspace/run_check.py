import subprocess
result = subprocess.run(['python3', 'check_pdf_libs.py'], capture_output=True, text=True, timeout=30, cwd='/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace')
print(result.stdout)
print(result.stderr)
