#!/bin/bash
echo "=== PATH ==="
echo $PATH
echo ""
echo "=== Check python and pip ==="
command -v python3 && python3 --version
command -v pip3 && pip3 --version
command -v pip && pip --version
echo ""
echo "=== Available tools ==="
for cmd in pdftotext pdfinfo mutool qpdf strings; do
    if command -v $cmd &> /dev/null; then
        echo "$cmd: available"
    else
        echo "$cmd: not found"
    fi
done
echo ""
echo "=== Try strings on PDF ==="
cat "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/2f424c6d-41c4-4383-9882-691f9a132244/user-data/uploads/杨佳文-java后端-v8.pdf" | tr -c '[:print:]\n' ' ' | tr -s ' ' | head -200
