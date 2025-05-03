import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def search_google_for_pdf(query, num_pages=2):
    urls = []
    for page in range(num_pages):
        start = page * 10
        url = f"https://www.google.com/search?q={query}+SDS+filetype:pdf&start={start}"
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        for a in soup.select("a"):
            href = a.get("href", "")
            if "url?q=" in href and ".pdf" in href:
                clean = href.split("url?q=")[1].split("&")[0]
                if clean not in urls:
                    urls.append(clean)
    return urls

def extract_hazards_from_pdf(pdf_content):
    text = ""
    try:
        with fitz.open(stream=pdf_content, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
    except Exception as e:
        return None

    hazards = re.findall(r"(H[2-4]\d{2})", text)
    section13 = ""
    if "SECTION 13" in text.upper():
        section_texts = re.split(r"SECTION \d+", text.upper())
        for block in section_texts:
            if block.startswith("13"):
                section13 = block.strip()
                break
    return {
        "hazard_codes": list(set(hazards)) or ["not found"],
        "disposal": section13.strip()[:1000] or "not found"
    }

def scrape_google_fallback(product_name):
    print(f"🔍 Google fallback scraping for: {product_name}")
    results = search_google_for_pdf(product_name)
    for pdf_url in results:
        try:
            pdf_response = requests.get(pdf_url, timeout=10)
            if "application/pdf" in pdf_response.headers.get("Content-Type", ""):
                parsed = extract_hazards_from_pdf(pdf_response.content)
                if parsed:
                    return {
                        "source": "Google SDS",
                        "hazards": parsed["hazard_codes"],
                        "disposal": parsed["disposal"],
                        "sds_url": pdf_url,
                        "data_quality": "partial" if "not found" in parsed["hazard_codes"] else "parsed"
                    }
        except Exception as e:
            print(f"⚠️ Failed to process {pdf_url}: {e}")
    return None
