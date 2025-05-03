import os
import re
import requests
import fitz  # PyMuPDF
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from firebase_admin import credentials, firestore, initialize_app

app = Flask(__name__)

# Firebase init (corrected method)
import firebase_admin
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    initialize_app(cred)
db = firestore.client()
products_ref = db.collection('products')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
}

def search_google_for_sds(product_name):
    query = f"{product_name} SDS filetype:pdf"
    for start in [0, 10]:
        search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}&start={start}"
        resp = requests.get(search_url, headers=HEADERS)
        if resp.status_code != 200:
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a['href']
            match = re.search(r"/url\?q=(https?[^&]+)", href)
            if match:
                candidate = match.group(1)
                if candidate.lower().endswith(".pdf"):
                    head = requests.head(candidate, allow_redirects=True, headers=HEADERS)
                    if 'application/pdf' in head.headers.get('Content-Type', ''):
                        return candidate
    return None

def extract_data_from_pdf(pdf_url):
    try:
        response = requests.get(pdf_url, headers=HEADERS)
        if response.status_code != 200:
            return None
        with open("temp_sds.pdf", "wb") as f:
            f.write(response.content)
        doc = fitz.open("temp_sds.pdf")
        text = "\n".join(page.get_text() for page in doc)
        os.remove("temp_sds.pdf")

        hazard_codes = re.findall(r"H[2-4]\d{2}", text)
        disposal_match = re.search(r"(?i)section\s*13.*?(disposal[^:]*):(.*?)(?=\n\s*\d{1,2}[^\d]|$)", text, re.DOTALL)
        disposal_text = disposal_match.group(2).strip() if disposal_match else "not found"

        return {
            "hazards": list(set(hazard_codes)) or ["not found"],
            "disposal": disposal_text,
            "sds_url": pdf_url,
            "source": "google_pdf"
        }
    except:
        return None

def try_html_sds(product_name):
    query = f"{product_name} SDS site:chemicalsafety.com"
    search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
    resp = requests.get(search_url, headers=HEADERS)
    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.find_all("a", href=True):
        match = re.search(r"/url\?q=(https://www\.chemicalsafety\.com[^&]+)", a["href"])
        if match:
            page_url = match.group(1)
            page = requests.get(page_url, headers=HEADERS)
            if page.status_code != 200:
                continue
            page_soup = BeautifulSoup(page.text, "html.parser")
            text = page_soup.get_text(separator="\n")
            hazard_codes = re.findall(r"H[2-4]\d{2}", text)
            disposal = "not found"
            if "section 13" in text.lower():
                disposal = "disposal guidance available on site"
            return {
                "hazards": list(set(hazard_codes)) or ["not found"],
                "disposal": disposal,
                "sds_url": page_url,
                "source": "chemical_safety_html"
            }
    return None

def save_to_firestore(product_name, data):
    required = ["hazards", "disposal", "sds_url"]
    missing = any(data.get(k) in [None, "not found"] for k in required)
    product_doc = {
        "name": product_name,
        "hazards": data.get("hazards", ["not found"]),
        "disposal": data.get("disposal", "not found"),
        "sds_url": data.get("sds_url", ""),
        "source": data.get("source", "unknown"),
        "image": "not found",
        "description": "not found",
        "score": "not found",
        "missingFields": missing
    }
    products_ref.document(product_name.lower()).set(product_doc)

@app.route("/")
def health():
    return "EcoRank scraper is live."

@app.route("/scrape", methods=["GET"])
def scrape():
    product_name = request.args.get("productName")
    if not product_name:
        return jsonify({"error": "Missing productName"}), 400

    existing_doc = products_ref.document(product_name.lower()).get()
    if existing_doc.exists:
        return jsonify(existing_doc.to_dict())

    pdf_url = search_google_for_sds(product_name)
    if pdf_url:
        data = extract_data_from_pdf(pdf_url)
        if data:
            save_to_firestore(product_name, data)
            return jsonify(data)

    html_data = try_html_sds(product_name)
    if html_data:
        save_to_firestore(product_name, html_data)
        return jsonify(html_data)

    return jsonify({"error": "No SDS found in Google results"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
