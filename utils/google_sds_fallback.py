import re
import time
import fitz
import requests
import random
from bs4 import BeautifulSoup
from urllib.parse import quote

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X)...",
    "Mozilla/5.0 (iPhone; CPU iPhone OS)..."
]

def get_random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml",
        "Referer": "https://www.google.com/"
    }

def search_google_for_sds_pdf(product_name):
    session = requests.Session()
    query = f"{product_name} SDS filetype:pdf"
    url = f"https://www.google.com/search?q={quote(query)}"
    resp = session.get(url, headers=get_random_headers(), timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    links = [a['href'] for a in soup.find_all("a", href=True)]

    for href in links:
        match = re.search(r"/url\?q=(https?[^&]+)", href)
        if match:
            pdf_url = match.group(1)
            if pdf_url.endswith(".pdf"):
                try:
                    head = session.head(pdf_url, headers=get_random_headers(), timeout=10, allow_redirects=True)
                    if "application/pdf" in head.headers.get("Content-Type", ""):
                        return pdf_url
                except:
                    continue
    return None

def extract_sds_data_from_pdf(pdf_url):
    try:
        response = requests.get(pdf_url, headers=get_random_headers(), timeout=20)
        doc = fitz.open(stream=response.content, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)

        hazard_codes = list(set(re.findall(r"\bH[2-4]\d{2}\b", text)))

        disposal = "not found"
        patterns = [
            r"13\.\s*Disposal.*?\n(.*?)(?=\n\d+\.)",
            r"SECTION\s*13.*?Disposal.*?\n(.*?)(?=SECTION\s*\d+)",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE | re.DOTALL)
            if match:
                disposal = match.group(1).strip()
                break

        return {
            "hazards": hazard_codes or ["not found"],
            "disposal": disposal,
            "sds_url": pdf_url,
            "source": "google_sds_scraper"
        }
    except Exception as e:
        print("⚠️ PDF extract error:", e)
        return None
