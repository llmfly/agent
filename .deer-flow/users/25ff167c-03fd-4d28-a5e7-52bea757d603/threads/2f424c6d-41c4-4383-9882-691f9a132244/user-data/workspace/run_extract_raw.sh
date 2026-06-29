#!/bin/bash
python3 -c "
with open('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/2f424c6d-41c4-4383-9882-691f9a132244/user-data/uploads/杨佳文-java后端-v8.pdf','rb') as f:
    d = f.read(200)
for i in range(0,len(d),16):
    hexs = ' '.join(f'{b:02x}' for b in d[i:i+16])
    ascii_str = ''.join(chr(b) if 32<=b<127 else '.' for b in d[i:i+16])
    print(f'{i:08x}  {hexs}  |{ascii_str}|')
"
