import os
import re
import requests
import fitz  # PyMuPDF
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from firebase_admin import credentials, firestore, initialize_app
from urllib.parse import quote, unquote
import firebase_admin

app = Flask(__name__)

# Firebase setup
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
db = firestore.client()
products_ref = db.collection('products')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
}

def get_google_results(product_name):
    for page in range(2):  # first two pages
        start = page * 10
        query = f"{product_name} SDS filetype:pdf"
        search_url = f"https://www.google.com/search?q={quote(query)}&start={start}"
        resp = requests.get(search_url, headers=HEADERS)
        if resp.status_code != 200:
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a['href']
            match = re.search(r"/url\?q=(https?[^&]+)", href)
            if match:
                url = unquote(match.group(1))
                if "sds" in url.lower() or url.lower().endswith(".pdf"):
                    yield url

def extract_data_from_pdf(url):
    try:
        res = requests.get(url, headers=HEADERS)
        if res.status_code != 200 or "application/pdf" not in res.headers.get("Content-Type", ""):
            return None

        with open("temp.pdf", "wb") as f:
            f.write(res.content)

        doc = fitz.open("temp.pdf")
        text = "\n".join([page.get_text() for page in doc])
        doc.close()
        os.remove("temp.pdf")

        hazard_codes = re.findall(r"H[2-4]\d{2}", text)
        section_13 = re.search(r"(Section\s*13.*?)(Section\s*\d+|$)", text, re.DOTALL | re.IGNORECASE)
        disposal = section_13.group(1).strip() if section_13 else "not found"

        return {
            "hazards": list(set(hazard_codes)) or ["not found"],
            "disposal": disposal,
            "sds_url": url,
            "source": "google_sds_pdf"
        }
    except Exception as e:
        return None

def extract_data_from_html(url):
    try:
        res = requests.get(url, headers=HEADERS)
        if res.status_code != 200 or "text/html" not in res.headers.get("Content-Type", ""):
            return None

        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text(separator="\n")

        hazard_codes = re.findall(r"H[2-4]\d{2}", text)
        section_13 = re.search(r"(Section\s*13.*?)(Section\s*\d+|$)", text, re.DOTALL | re.IGNORECASE)
        disposal = section_13.group(1).strip() if section_13 else "not found"

        return {
            "hazards": list(set(hazard_codes)) or ["not found"],
            "disposal": disposal,
            "sds_url": url,
            "source": "google_sds_html"
        }
    except Exception as e:
        return None

def save_to_firestore(product_name, data):
    record = {
        "name": product_name,
        "hazards": data.get("hazards", ["not found"]),
        "disposal": data.get("disposal", "not found"),
        "sds_url": data.get("sds_url", ""),
        "source": data.get("source", "unknown"),
        "image": "not found",
        "description": "not found",
        "score": "not found"
    }
    products_ref.document(product_name.lower()).set(record)

@app.route("/")
def index():
    return "EcoRank scraper is live."

@app.route("/scrape", methods=["GET"])
def scrape():
    product_name = request.args.get("productName")
    if not product_name:
        return jsonify({"error": "Missing productName"}), 400

    existing = products_ref.document(product_name.lower()).get()
    if existing.exists:
        return jsonify(existing.to_dict())

    for url in get_google_results(product_name):
        if url.lower().endswith(".pdf"):
            data = extract_data_from_pdf(url)
        else:
            data = extract_data_from_html(url)

        if data:
            save_to_firestore(product_name, data)
            return jsonify(data)

    return jsonify({"error": "No SDS found in Google results"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
