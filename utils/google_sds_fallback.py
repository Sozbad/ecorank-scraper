import os
import re
import requests
import fitz  # PyMuPDF
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
}


def search_google_for_sds_pdf(product_name):
    try:
        query = f"{product_name} SDS filetype:pdf"
        for page in range(0, 20, 10):  # page 0 and 1 (first 20 results)
            search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}&start={page}"
            resp = requests.get(search_url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select("a[href]"):
                href = a["href"]
                match = re.search(r"/url\?q=(https?[^&]+)", href)
                if match:
                    pdf_url = match.group(1)
                    if pdf_url.lower().endswith(".pdf"):
                        head = requests.head(pdf_url, allow_redirects=True, headers=HEADERS, timeout=10)
                        if "application/pdf" in head.headers.get("Content-Type", ""):
                            return pdf_url
    except Exception:
        pass
    return None


def extract_sds_data_from_pdf(pdf_url):
    try:
        response = requests.get(pdf_url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return None

        with open("temp_sds.pdf", "wb") as f:
            f.write(response.content)

        doc = fitz.open("temp_sds.pdf")
        text = "\n".join(page.get_text() for page in doc)
        os.remove("temp_sds.pdf")

        hazard_codes = re.findall(r"\bH[2-4]\d{2}\b", text)
        section_13 = re.search(r"(?:13\.\s*Disposal(?:\s*Considerations)?\s*\n)(.*?)(?:\n\d+\.\s|\Z)", text, re.DOTALL | re.IGNORECASE)
        disposal_text = section_13.group(1).strip() if section_13 else "not found"

        return {
            "hazards": list(set(hazard_codes)) or ["not found"],
            "disposal": disposal_text,
            "sds_url": pdf_url,
            "source": "google_sds_scraper"
        }
    except Exception:
        return None
