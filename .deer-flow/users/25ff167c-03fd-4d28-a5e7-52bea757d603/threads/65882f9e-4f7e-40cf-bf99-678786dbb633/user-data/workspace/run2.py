import subprocess, sys, importlib

# 首先确保python-docx已安装
try:
    import docx
except ImportError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'python-docx', '-q'])

# 执行主脚本
result = subprocess.run([sys.executable, '/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/65882f9e-4f7e-40cf-bf99-678786dbb633/user-data/workspace/generate_report.py'], capture_output=False, cwd='/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/65882f9e-4f7e-40cf-bf99-678786dbb633/user-data/workspace')
print(f"Return code: {result.returncode}")
