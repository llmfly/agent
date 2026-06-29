#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查Python环境并生成DOCX"""

import importlib, subprocess, sys, os

# 尝试安装python-docx
try:
    import docx
    print("python-docx已安装")
except ImportError:
    print("正在安装python-docx...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'python-docx', '-q'])
    import docx
    print("安装成功")

# 导入并执行主脚本
script_path = '/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/65882f9e-4f7e-40cf-bf99-678786dbb633/user-data/workspace/generate_report.py'
exec(open(script_path, encoding='utf-8').read())
