import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from sds_parser import parse_sds_pdf

HEADERS = {"User-Agent": "Mozilla/5.0"}

def search_google_for_pdf(product_name):
    search_url = f"https://www.google.com/search?q={product_name}+SDS+filetype:pdf"
    print(f"🔎 Searching Google for: {search_url}")
    try:
        res = requests.get(search_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        links = soup.select("a")
        pdf_links = []
        for link in links:
            href = link.get("href", "")
            if ".pdf" in href:
                direct_link = extract_pdf_url(href)
                if direct_link:
                    pdf_links.append(direct_link)
            if len(pdf_links) >= 10:
                break
        print(f"🔗 Found {len(pdf_links)} PDF links")
        return pdf_links
    except Exception as e:
        print(f"❌ Google SDS search error: {e}")
        return []

def extract_pdf_url(href):
    match = re.search(r"https?://[^\s\"']+\.pdf", href)
    return match.group(0) if match else None

def google_sds_fallback(product_name):
    print(f"🌐 Trying Google SDS fallback for: {product_name}")
    pdf_links = search_google_for_pdf(product_name)
    for pdf_url in pdf_links:
        print(f"📎 Trying PDF: {pdf_url}")
        try:
            parsed = parse_sds_pdf(pdf_url)
            if parsed:
                hazards = parsed.get("hazard_codes", [])
                return {
                    "source": "Google SDS",
                    "sds_url": pdf_url,
                    "hazard_codes": hazards,
                    "disposal": parsed.get("disposal", "not found"),
                    "data_quality": parsed.get("data_quality", "unknown")
                }
        except Exception as e:
            print(f"❌ PDF parse failed: {e}")
            continue
    print("❌ No valid SDS found from Google fallback.")
    return None
