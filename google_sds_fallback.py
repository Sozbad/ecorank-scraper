import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import quote
from PyPDF2 import PdfReader
from io import BytesIO
import time

def extract_hazard_codes(text):
    return list(set(re.findall(r'H[2-4]\d{2}', text)))

def extract_disposal_section(text):
    match = re.search(r'(?:Section\s*13[\.:]?\s*)(.*?)((?:Section\s*\d{1,2}[\.:])|$)', text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else "not found"

def extract_text_from_pdf(url):
    try:
        response = requests.get(url, timeout=15)
        if response.ok:
            reader = PdfReader(BytesIO(response.content))
            return "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
    except:
        pass
    return ""

def search_google_sds_fallback(product_name):
    headers = {"User-Agent": "Mozilla/5.0"}
    query = f"{product_name} SDS filetype:pdf"

    for page in range(0, 2):  # Pages 1 and 2
        start = page * 10
        url = f"https://www.google.com/search?q={quote(query)}&start={start}"
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        links = [a["href"] for a in soup.find_all("a", href=True) if a["href"].endswith(".pdf")]

        for pdf_url in links:
            text = extract_text_from_pdf(pdf_url)
            if not text:
                continue

            hazard_codes = extract_hazard_codes(text)
            disposal = extract_disposal_section(text)

            return {
                "name": product_name,
                "hazards": hazard_codes if hazard_codes else "not found",
                "disposal": disposal,
                "sds_url": pdf_url,
                "source": "Google SDS fallback",
                "score": 0
            }

        time.sleep(1)

    return None
