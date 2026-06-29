import os, sys
os.chdir('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace')
r = os.system('python3 -c "import sys; print(sys.executable); print(sys.path)"')
print("Done, r=", r)
