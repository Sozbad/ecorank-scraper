import fitz  # PyMuPDF

def parse_sds_pdf(pdf_path):
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        print(f"❌ Failed to parse PDF: {e}")
        return None
