# Quick check - read first few bytes of PDF to confirm it's a valid PDF
with open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/8867365d-0dd3-41cc-9b98-86d973e9da25/user-data/uploads/崔亚飞.pdf", "rb") as f:
    header = f.read(100)
    print("Header:", repr(header[:50]))
    
with open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/8867365d-0dd3-41cc-9b98-86d973e9da25/user-data/uploads/杨佳文-java后端-v8.pdf", "rb") as f:
    header = f.read(100)
    print("Header:", repr(header[:50]))

# Try to read the PDF text via subprocess
import subprocess
r = subprocess.run(["python3", "-c", "import sys; print(sys.path)"], capture_output=True, text=True)
print(r.stdout[:500])
