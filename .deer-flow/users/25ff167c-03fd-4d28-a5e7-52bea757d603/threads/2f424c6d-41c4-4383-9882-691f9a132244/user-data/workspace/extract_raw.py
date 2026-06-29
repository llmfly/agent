#!/usr/bin/env python3
"""Try to extract text from PDF using only built-in modules (zlib)."""
import zlib
import re
import os

pdf_path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/2f424c6d-41c4-4383-9882-691f9a132244/user-data/uploads/杨佳文-java后端-v8.pdf"
with open(pdf_path, "rb") as f:
    data = f.read()

print(f"File size: {len(data)} bytes")
print(f"First bytes: {data[:20].hex()}")

# PDF is a binary file. Let's try to find and decompress streams
# Find stream...endstream sections
streams_found = 0
for m in re.finditer(rb'stream\s(.+?)endstream', data, re.DOTALL):
    raw = m.group(1).strip()
    streams_found += 1
    
    # Try to decompress with FlateDecode (zlib)
    try:
        decompressed = zlib.decompress(raw)
        # Try to decode as text
        for enc in ['utf-8', 'latin-1', 'gbk', 'gb2312', 'big5']:
            try:
                text = decompressed.decode(enc)
                # Check if it contains meaningful content
                if any(c.isalpha() for c in text) and len(text) > 50:
                    print(f"\n=== Stream {streams_found} (decompressed, encoded as {enc}) ===")
                    print(text[:1000])
                    break
            except:
                continue
    except (zlib.error, Exception):
        pass
    
    if streams_found > 20:
        break

print(f"\nTotal streams found: {streams_found}")

# Also try: raw text might use hex encoding
for m in re.finditer(rb'<([0-9a-fA-F]+)>', data):
    hex_str = m.group(1).decode('ascii', errors='ignore')
    if len(hex_str) > 20 and len(hex_str) % 2 == 0:
        try:
            decoded = bytes.fromhex(hex_str)
            for enc in ['utf-16-be', 'utf-16-le', 'gbk', 'big5']:
                try:
                    text = decoded.decode(enc)
                    if any('\u4e00' <= c <= '\u9fff' for c in text):
                        print(f"HEX ({enc}): {text[:200]}")
                        break
                except:
                    continue
        except:
            pass
