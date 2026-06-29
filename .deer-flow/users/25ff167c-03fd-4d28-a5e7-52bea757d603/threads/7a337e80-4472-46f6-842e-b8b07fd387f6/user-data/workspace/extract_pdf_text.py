import subprocess
import sys

# Try pdftotext first
try:
    for f in ["杨佳文-java后端-v8.pdf", "崔亚飞.pdf"]:
        infile = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/7a337e80-4472-46f6-842e-b8b07fd387f6/user-data/uploads/{f}"
        outfile = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/7a337e80-4472-46f6-842e-b8b07fd387f6/user-data/workspace/{f}.txt"
        result = subprocess.run(["pdftotext", infile, outfile], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Successfully extracted {f}")
        else:
            print(f"Failed to extract {f}: {result.stderr}")
except FileNotFoundError:
    print("pdftotext not found, trying alternative...")
    # Try python libraries
    try:
        import PyPDF2
        for f in ["杨佳文-java后端-v8.pdf", "崔亚飞.pdf"]:
            infile = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/7a337e80-4472-46f6-842e-b8b07fd387f6/user-data/uploads/{f}"
            outfile = f"/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/7a337e80-4472-46f6-842e-b8b07fd387f6/user-data/workspace/{f}.txt"
            with open(infile, 'rb') as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            with open(outfile, 'w', encoding='utf-8') as f_out:
                f_out.write(text)
            print(f"Extracted {len(text)} chars from {f}")
    except ImportError:
        print("PyPDF2 not found")
        try:
            import pdfminer
            print("pdfminer found")
        except ImportError:
            print("No PDF library available")
