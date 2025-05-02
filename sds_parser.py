import fitz  # PyMuPDF
import requests
import re

def extract_text_from_pdf_url(pdf_url):
    try:
        response = requests.get(pdf_url, timeout=15)
        if response.status_code != 200:
            print(f"❌ Failed to download PDF: {response.status_code}")
            return None
        doc = fitz.open("pdf", response.content)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        return full_text
    except Exception as e:
        print(f"❌ PDF extract error: {e}")
        return None

def extract_sds_fields_from_text(text):
    hazard_codes = list(set(re.findall(r"H\d{3}", text)))
    section_13_text = "not found"
    section_match = re.search(r"(13\.?\s*DISPOSAL.*?)(14\.|SECTION 14|TRANSPORT)", text, re.IGNORECASE | re.DOTALL)
    if section_match:
        section_13_raw = section_match.group(1).strip()
        section_13_text = section_13_raw[:500]
    return {
        "hazard_codes": hazard_codes or [],
        "disposal": section_13_text.strip() if section_13_text else "not found",
        "data_quality": "parsed from SDS"
    }

def parse_sds_pdf(pdf_url):
    print(f"📄 Parsing SDS: {pdf_url}")
    text = extract_text_from_pdf_url(pdf_url)
    if not text:
        return {"hazard_codes": [], "disposal": "not found", "data_quality": "unreadable"}
    return extract_sds_fields_from_text(text)
