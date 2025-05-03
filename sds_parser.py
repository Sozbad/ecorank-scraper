import fitz  # PyMuPDF

def parse_sds_pdf(pdf_path):
    try:
        text = ""
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        print(f"❌ PDF parse error: {e}")
        return None
