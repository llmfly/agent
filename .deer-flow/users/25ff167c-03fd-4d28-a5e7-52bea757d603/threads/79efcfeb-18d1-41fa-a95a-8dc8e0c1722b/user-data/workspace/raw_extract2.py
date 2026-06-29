#!/usr/bin/env python3
import subprocess, os, re, unicodedata

os.chdir('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/workspace')

with open('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/79efcfeb-18d1-41fa-a95a-8dc8e0c1722b/user-data/uploads/崔亚飞.pdf', 'rb') as f:
    data = f.read()

# Try different approaches
# 1. Extract all high-ASCII and CJK sequences
text = data.decode('latin-1')

# Find CJK characters and surrounding text
cjk_blocks = []
current = []
for i, ch in enumerate(text):
    if ord(ch) >= 0x4e00 or ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789，。、：；！？（）【】""''—…·/\n\t ':
        current.append(ch)
    else:
        if current:
            block = ''.join(current)
            if len(block) > 10:
                cjk_blocks.append(block)
            current = []

if current:
    block = ''.join(current)
    if len(block) > 10:
        cjk_blocks.append(block)

print("=== Extracted readable content ===")
for block in cjk_blocks:
    print(block[:500])
    print("---")
