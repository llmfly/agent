# Just try importing and seeing what's available
import importlib
for mod_name in ['fitz', 'PyPDF2', 'pypdf', 'pdfminer', 'pdfplumber', 'pdfminer.high_level', 'pdfminer.pdfparser', 'pdfminer.converter', 'pdfminer.layout', 'pdfminer.utils']:
    try:
        importlib.import_module(mod_name)
        print(f"{mod_name}: AVAILABLE")
    except ImportError:
        print(f"{mod_name}: NOT available")
