
import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF
import re
import tempfile
import os

GOOGLE_SEARCH_URL = "https://www.google.com/search"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def google_search(query):
    response = requests.get(GOOGLE_SEARCH_URL, params={"q": query}, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")
    results = soup.select("a")
    for tag in results:
        href = tag.get("href")
        if href and "/url?q=" in href:
            url = href.split("/url?q=")[1].split("&")[0]
            if "chemicalsafety.com/sds/" in url:
                return url
    return None

def fetch_chemical_safety_data(url):
    try:
        res = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(res.text, "html.parser")
        hazards = []
        for tag in soup.select(".sds-hazards .sds-hazard"):
            code = tag.select_one(".hazard-code")
            desc = tag.select_one(".hazard-desc")
            if code and desc:
                hazards.append({
                    "code": code.text.strip(),
                    "description": desc.text.strip()
                })
        if hazards:
            return {
                "source": url,
                "hazards": hazards
            }
    except Exception as e:
        print(f"[!] Failed to fetch from Chemical Safety: {e}")
    return None

def extract_hazard_codes_from_pdf(pdf_path):
    codes = set()
    try:
        with fitz.open(pdf_path) as doc:
            text = "".join(page.get_text() for page in doc)
            found = re.findall(r"H[2-4]\d{2}", text)
            codes.update(found)
    except Exception as e:
        print(f"[!] PDF parse error: {e}")
    return list(codes)

def google_pdf_sds_search(product_name):
    query = f"{product_name} SDS filetype:pdf"
    response = requests.get("https://www.google.com/search", params={"q": query}, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")
    links = soup.select("a")
    for tag in links:
        href = tag.get("href")
        if href and "url?q=" in href and "pdf" in href:
            url = href.split("/url?q=")[1].split("&")[0]
            if url.endswith(".pdf"):
                print(f"[+] Found PDF SDS: {url}")
                return url
    return None

def download_and_parse_pdf(pdf_url):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            r = requests.get(pdf_url, stream=True)
            for chunk in r.iter_content(1024):
                tmp.write(chunk)
            tmp_path = tmp.name
        hazards = extract_hazard_codes_from_pdf(tmp_path)
        os.unlink(tmp_path)
        return {
            "source": pdf_url,
            "hazards": [{"code": h, "description": "Hazard code from PDF"} for h in hazards]
        } if hazards else None
    except Exception as e:
        print(f"[!] PDF download/parse error: {e}")
        return None

def scrape_product(product_name):
    cs_url = google_search(f"{product_name} SDS site:chemicalsafety.com")
    if cs_url:
        result = fetch_chemical_safety_data(cs_url)
        if result:
            return result

    pdf_url = google_pdf_sds_search(product_name)
    if pdf_url:
        pdf_result = download_and_parse_pdf(pdf_url)
        if pdf_result:
            return pdf_result

    return {"error": "No SDS found"}
