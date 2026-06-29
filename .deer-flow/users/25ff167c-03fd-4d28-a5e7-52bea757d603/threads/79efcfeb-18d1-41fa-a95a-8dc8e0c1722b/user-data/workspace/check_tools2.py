import subprocess
import os
os.chdir('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace')

# Check tools
r = subprocess.run(['which', 'pdftotext', 'pdftotext', 'python3', 'pdftotext'], capture_output=True, text=True)
print(r.stdout)

# Check python
r = subprocess.run(['python3', '--version'], capture_output=True, text=True)
print(r.stdout.strip())

# List pip packages
r = subprocess.run([sys.executable, '-m', 'pip', 'list', '--format=columns'], capture_output=True, text=True)
print(r.stdout[:2000])
print(r.stderr[:2000])
