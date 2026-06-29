#!/usr/bin/env python3
import pdfminer

# Try using pdfminer which may already be installed
from pdfminer.high_level import extract_text
text = extract_text('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/ec110bfb-2110-4334-b8e8-96f817b5efd8/user-data/uploads/崔亚飞.pdf')
print(text[:2000])
