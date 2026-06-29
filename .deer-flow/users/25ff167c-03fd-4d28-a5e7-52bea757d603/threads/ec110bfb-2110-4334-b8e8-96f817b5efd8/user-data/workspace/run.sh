# install pymupdf
python3 -m pip install pymupdf 2>&1
echo "---"
# test
python3 -c "import fitz; print('OK')" 2>&1
echo "---"
# extract
python3 -c "
import fitz
doc = fitz.open('/data/intelli/engine/.deer-flow/users/25ff167c-03fd-4d28-a5e7-52bea757d603/threads/ec110bfb-2110-4334-b8e8-96f817b5efd8/user-data/uploads/崔亚飞.pdf')
print('Pages:', doc.page_count)
for i, page in enumerate(doc):
    text = page.get_text()
    print(f'---Page {i+1}---')
    print(text[:2000])
doc.close()
" 2>&1