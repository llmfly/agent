#!/usr/bin/env python3
"""Extract text from docx file using multiple methods."""
import sys
import zipfile
import os
import xml.etree.ElementTree as ET

filepath = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/4701a749-5761-463e-b5d0-8719d0d7c800/user-data/uploads/Doc1.docx"
outpath = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/4701a749-5761-463e-b5d0-8719d0d7c800/user-data/workspace/docx_content.txt"

# Method 1: Use zipfile to extract the XML content
try:
    with zipfile.ZipFile(filepath, 'r') as z:
        # List all files in the archive
        with open(outpath, 'w', encoding='utf-8') as f:
            f.write("=== ZIP Contents ===\n")
            for name in z.namelist():
                f.write(f"  {name} ({z.getinfo(name).file_size} bytes)\n")
            
            # Extract document.xml
            if 'word/document.xml' in z.namelist():
                f.write("\n\n=== word/document.xml ===\n")
                xml_content = z.read('word/document.xml').decode('utf-8')
                # Simple strip of XML tags
                text_parts = []
                for line in xml_content.split('<'):
                    if line.startswith('w:t'):
                        # Extract text content between > and <
                        start = line.find('>')
                        end = line.find('<', start+1)
                        if start >= 0:
                            text = line[start+1:end] if end > start else line[start+1:]
                            if text.strip():
                                text_parts.append(text.strip())
                    elif line.startswith('w:p'):
                        text_parts.append('\n')
                f.write(' '.join(text_parts))
            
            # Extract any other interesting XML files
            for name in z.namelist():
                if name.endswith('.xml') and 'document' in name.lower():
                    f.write(f"\n\n=== {name} ===\n")
                    content = z.read(name).decode('utf-8')
                    # Remove XML namespace stuff for readability
                    content = content.replace(' xmlns:', '\nxmlns:')
                    f.write(content[:5000])
                    
except Exception as e:
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(f"Error: {e}")

print(f"Written to {outpath}")
