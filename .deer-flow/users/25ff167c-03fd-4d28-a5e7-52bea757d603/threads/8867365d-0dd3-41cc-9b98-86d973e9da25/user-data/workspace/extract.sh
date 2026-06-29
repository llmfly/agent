#!/bin/bash
echo "=== 崔亚飞.pdf ==="
pdftotext /data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/8867365d-0dd3-41cc-9b98-86d973e9da25/user-data/uploads/崔亚飞.pdf - 2>&1 | head -500
echo ""
echo "=== 杨佳文-java后端-v8.pdf ==="
pdftotext /data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/8867365d-0dd3-41cc-9b98-86d973e9da25/user-data/uploads/杨佳文-java后端-v8.pdf - 2>&1 | head -500
