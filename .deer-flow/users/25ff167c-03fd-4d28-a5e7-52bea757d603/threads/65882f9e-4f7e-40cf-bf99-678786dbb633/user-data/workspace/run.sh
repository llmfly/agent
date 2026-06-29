#!/usr/bin/env python3
"""安装依赖并运行脚本"""
import subprocess, sys

subprocess.run([sys.executable, '-m', 'pip', 'install', 'python-docx', '-q'])
subprocess.run([sys.executable, '/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/65882f9e-4f7e-40cf-bf99-678786dbb633/user-data/workspace/generate_report.py'])
