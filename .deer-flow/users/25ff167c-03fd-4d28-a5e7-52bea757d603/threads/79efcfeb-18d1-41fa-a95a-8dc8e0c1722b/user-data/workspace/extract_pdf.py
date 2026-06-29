import subprocess
import sys

# Try pdftotext first
try:
    result = subprocess.run(['pdftotext', '/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/uploads/崔亚飞.pdf', '-'], 
                           capture_output=True, text=True, timeout=30)
    if result.returncode == 0 and result.stdout.strip():
        print("=== 崔亚飞.pdf ===")
        print(result.stdout[:5000])
    else:
        print("pdftotext failed for 崔亚飞")
except:
    print("pdftotext not available for 崔亚飞")

print("\n\n")

try:
    result = subprocess.run(['pdftotext', '/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/uploads/杨佳文-java后端-v8.pdf', '-'], 
                           capture_output=True, text=True, timeout=30)
    if result.returncode == 0 and result.stdout.strip():
        print("=== 杨佳文-java后端-v8.pdf ===")
        print(result.stdout[:5000])
    else:
        print("pdftotext failed for 杨佳文")
except:
    print("pdftotext not available for 杨佳文")
