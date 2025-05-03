import re
import requests
import fitz  # PyMuPDF
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
}


def search_google_for_sds_pdf(product_name):
    query = f"{product_name} SDS filetype:pdf"
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select("a[href]"):
            href = a["href"]
            match = re.search(r"/url\?q=(https?[^&]+)", href)
            if match:
                pdf_url = match.group(1)
                if pdf_url.lower().endswith(".pdf"):
                    head = requests.head(pdf_url, allow_redirects=True, headers=HEADERS)
                    if "application/pdf" in head.headers.get("Content-Type", ""):
                        return pdf_url
        return None
    except Exception:
        return None


def extract_sds_data_from_pdf(pdf_url):
    try:
        pdf_response = requests.get(pdf_url, headers=HEADERS, timeout=15)
        if pdf_response.status_code != 200:
            return None

        with open("temp_sds.pdf", "wb") as f:
            f.write(pdf_response.content)

        doc = fitz.open("temp_sds.pdf")
        text = "\n".join(page.get_text() for page in doc)
        doc.close()

        hazard_codes = re.findall(r"H[2-4]\d{2}", text)
        unique_codes = sorted(set(hazard_codes))

        match = re.search(r"13\s*(\.|:)?\s*(Disposal Considerations.*?)\n\d{1,2}[\.:]", text, re.DOTALL | re.IGNORECASE)
        disposal_text = match.group(2).strip() if match else "not found"

        return {
            "hazards": unique_codes or ["not found"],
            "disposal": disposal_text,
            "sds_url": pdf_url,
            "source": "google_sds_fallback"
        }

    except Exception:
        return None
