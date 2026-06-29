#!/bin/bash
# Check pdftotext
which pdftotext
echo "exit code: $?"

# Try to extract text from 崔亚飞.pdf
echo "=== 崔亚飞.pdf ==="
pdftotext /data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/8867365d-0dd3-41cc-9b98-86d973e9da25/user-data/uploads/崔亚飞.pdf -
echo ""
echo "=== EXIT: $? ==="

echo "=== 杨佳文-java后端-v8.pdf ==="
pdftotext /data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/8867365d-0dd3-41cc-9b98-86d973e9da25/user-data/uploads/杨佳文-java后端-v8.pdf -
echo ""
echo "=== EXIT: $? ==="
