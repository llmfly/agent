#!/usr/bin/env python3
import subprocess, os

os.chdir('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace')

# Run install and extract, capture all output to a file
script = '''
apt-get update -qq 2>/dev/null
apt-get install -y -qq poppler-utils 2>/dev/null
which pdftotext
pdftotext -layout /data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/uploads/崔亚飞.pdf -
'''

with open('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace/run.sh', 'w') as f:
    f.write('#!/bin/bash\n' + script)

os.chmod('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace/run.sh', 0o755)

result = subprocess.run("bash run.sh", shell=True, capture_output=True, text=True, timeout=120)
print("STDOUT:", result.stdout[:8000])
print("STDERR:", result.stderr[:500])
print("Return:", result.returncode)
