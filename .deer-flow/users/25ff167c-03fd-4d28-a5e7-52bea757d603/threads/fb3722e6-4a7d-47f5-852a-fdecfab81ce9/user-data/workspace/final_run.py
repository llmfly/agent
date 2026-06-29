import subprocess, sys, os

# Step 1: Install
subprocess.run([sys.executable, "-m", "pip", "install", "PyMuPDF"], capture_output=True)

# Step 2: Import and extract
sys.path.insert(0, "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/workspace")
exec(open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb3722e6-4a7d-47f5-852a-fdecfab81ce9/user-data/workspace/simple_extract.py").read())
