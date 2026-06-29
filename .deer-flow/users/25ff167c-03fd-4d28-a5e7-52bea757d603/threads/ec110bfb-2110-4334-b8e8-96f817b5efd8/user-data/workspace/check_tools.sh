# try to see what packages are available
python3 -m pip list 2>&1 | head -30
echo "---"
python3 --version 2>&1
echo "---"
python3 -c "import pdfminer; print('pdfminer available')" 2>&1
python3 -c "import fitz; print('fitz available')" 2>&1
python3 -c "import PyPDF2; print('PyPDF2 available')" 2>&1
python3 -c "import pdfplumber; print('pdfplumber available')" 2>&1
python3 -c "import pdfminer.high_level; print('pdfminer.high_level available')" 2>&1
