import fitz
doc = fitz.open("/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/fb8b40c6-d631-4820-8aad-210e687fd3e4/user-data/uploads/1201060226271-1Pys.pdf")
print(f"Pages: {doc.page_count}")
for i, page in enumerate(doc):
    text = page.get_text()
    print(f"\n=== PAGE {i+1} ===")
    print(text)
