
import os
import re
import requests
import fitz  # PyMuPDF
import firebase_admin
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import quote
from firebase_admin import credentials, firestore
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# Firebase setup
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
db = firestore.client()
products_ref = db.collection("products")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def run_playwright_google_search(query, max_pages=2):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        results = []
        for i in range(max_pages):
            start = i * 10
            url = f"https://www.google.com/search?q={quote(query)}&start={start}"
            page.goto(url)
            page.wait_for_timeout(1000)
            elements = page.query_selector_all("a")
            for a in elements:
                href = a.get_attribute("href")
                if href and "/url?q=" in href:
                    match = re.search(r"/url\?q=(https?[^&]+)", href)
                    if match:
                        results.append(match.group(1))
        browser.close()
        return results

def search_sds_pdf_url(product_name):
    links = run_playwright_google_search(f"{product_name} SDS filetype:pdf")
    for url in links:
        if url.lower().endswith(".pdf"):
            try:
                head = requests.head(url, headers=HEADERS, allow_redirects=True, timeout=5)
                if "application/pdf" in head.headers.get("Content-Type", ""):
                    return url
            except:
                continue
    return None

def extract_sds_text_from_pdf(pdf_url):
    try:
        res = requests.get(pdf_url, headers=HEADERS)
        with open("temp_sds.pdf", "wb") as f:
            f.write(res.content)
        doc = fitz.open("temp_sds.pdf")
        text = "\n".join([page.get_text() for page in doc])
        doc.close()
        os.remove("temp_sds.pdf")
        return text
    except:
        return ""

def parse_hazards_and_disposal(text):
    hazard_codes = list(set(re.findall(r"H[2-4]\d{2}", text)))
    section_13 = re.search(r"(13\.*\s*DISPOSAL.*?)(?=\n\d+\.|\Z)", text, re.DOTALL | re.IGNORECASE)
    disposal = section_13.group(1).strip() if section_13 else "not found"
    return hazard_codes or ["not found"], disposal or "not found"

def search_google_details(product_name):
    try:
        results = run_playwright_google_search(product_name)
        desc, image = "not found", "not found"
        for link in results:
            if "wikipedia.org" in link or "product" in link:
                try:
                    resp = requests.get(link, headers=HEADERS)
                    soup = BeautifulSoup(resp.text, "html.parser")
                    p = soup.find("p")
                    if p:
                        desc = p.text.strip()
                    img = soup.find("img")
                    if img and img.get("src"):
                        image = img["src"]
                    break
                except:
                    continue
        return { "description": desc, "image": image }
    except:
        return { "description": "not found", "image": "not found" }

def save_to_firestore(product_name, data):
    record = {
        "name": product_name,
        "hazards": data.get("hazards", ["not found"]),
        "disposal": data.get("disposal", "not found"),
        "sds_url": data.get("sds_url", ""),
        "source": data.get("source", "google_sds_scraper"),
        "image": data.get("image", "not found"),
        "description": data.get("description", "not found"),
        "score": "not found",
        "missingFields": []
    }
    for key in ["hazards", "disposal", "image", "description"]:
        if record[key] == "not found" or record[key] == ["not found"]:
            record["missingFields"].append(key)
    products_ref.document(product_name.lower()).set(record)

@app.route("/")
def health():
    return "EcoRank scraper running with Playwright."

@app.route("/scrape", methods=["GET"])
def scrape():
    product_name = request.args.get("productName")
    if not product_name:
        return jsonify({"error": "Missing productName"}), 400

    existing = products_ref.document(product_name.lower()).get()
    if existing.exists:
        return jsonify(existing.to_dict())

    pdf_url = search_sds_pdf_url(product_name)
    if not pdf_url:
        return jsonify({"error": "No SDS PDF found in Google results"}), 404

    text = extract_sds_text_from_pdf(pdf_url)
    if not text:
        return jsonify({"error": "Failed to read PDF"}), 500

    hazards, disposal = parse_hazards_and_disposal(text)
    data = {
        "hazards": hazards,
        "disposal": disposal,
        "sds_url": pdf_url,
        "source": "google_sds_scraper"
    }

    details = search_google_details(product_name)
    data.update(details)
    save_to_firestore(product_name, data)
    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
