import sys
sys.path.insert(0, '/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb8b40c6-d631-4820-8aad-210e687fd3e4/user-data/workspace')

# Check available modules
import importlib
for mod_name in ['fitz', 'PyPDF2', 'pypdf', 'pdfminer', 'pdfplumber', 'pdfminer.high_level', 'pdfminer.pdfparser', 'pdfminer.converter', 'pdfminer.layout', 'pdfminer.utils']:
    try:
        importlib.import_module(mod_name)
        print(f"{mod_name}: AVAILABLE")
    except ImportError:
        print(f"{mod_name}: NOT available")
