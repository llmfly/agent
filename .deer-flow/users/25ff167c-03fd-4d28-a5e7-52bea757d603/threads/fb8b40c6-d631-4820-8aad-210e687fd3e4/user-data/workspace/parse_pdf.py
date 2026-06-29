import fitz  # PyMuPDF
import os

pdf_path = "/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb8b40c6-d631-4820-8aad-210e687fd3e4/user-data/uploads/1201060226271-1Pys.pdf"

print(f"File exists: {os.path.exists(pdf_path)}")
print(f"File size: {os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 'N/A'}")

doc = fitz.open(pdf_path)
print(f"Number of pages: {doc.page_count}")

for i, page in enumerate(doc):
    text = page.get_text()
    print(f"\n{'='*60}")
    print(f"=== PAGE {i+1} ===")
    print(f"{'='*60}")
    print(text[:3000] if len(text) > 3000 else text)
