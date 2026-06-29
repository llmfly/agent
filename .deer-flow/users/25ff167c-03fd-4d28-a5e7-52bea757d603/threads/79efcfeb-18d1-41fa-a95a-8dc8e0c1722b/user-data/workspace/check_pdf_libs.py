import importlib
for mod_name in ['pdfminer', 'PyPDF2', 'pdfplumber', 'pdfminer.high_level', 'pdfminer.layout', 'pdfminer.utils', 'pikepdf', 'pdfminer.six', 'pdfminer.pdfpage', 'pdfminer.pdfparser', 'pdfminer.converter', 'pdfminer.pdfinterp']:
    try:
        importlib.import_module(mod_name)
        print(f"  {mod_name} - AVAILABLE")
    except ImportError:
        pass
