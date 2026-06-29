# 使用子进程执行Python脚本
import subprocess
import sys

result = subprocess.run([sys.executable, '/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/65882f9e-4f7e-40cf-bf99-678786dbb633/user-data/workspace/generate_report.py'], capture_output=True, text=True, cwd='/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/65882f9e-4f7e-40cf-bf99-678786dbb633/user-data/workspace')
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
print("Return code:", result.returncode)
