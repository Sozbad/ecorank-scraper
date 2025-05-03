import os
import re
import requests
import fitz  # PyMuPDF
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from firebase_admin import credentials, firestore, initialize_app

app = Flask(__name__)

# Firebase setup
if not firestore._apps:
    cred = credentials.ApplicationDefault()
    initialize_app(cred)
db = firestore.client()
products_ref = db.collection('products')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
}

def search_google_sds(product_name, max_pages=2):
    session = requests.Session()
    found_pdf = None

    for page in range(max_pages):
        start = page * 10
        query = f"{product_name} SDS filetype:pdf"
        search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}&start={start}"

        try:
            resp = session.get(search_url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a['href']
                match = re.search(r"/url\?q=(https?[^&]+)", href)
                if match:
                    pdf_url = match.group(1)
                    if ".pdf" in pdf_url.lower():
                        head = session.head(pdf_url, allow_redirects=True, headers=HEADERS, timeout=10)
                        if 'application/pdf' in head.headers.get('Content-Type', ''):
                            return pdf_url
        except Exception:
            continue

    return None

def extract_hazard_data_from_pdf(pdf_url):
    try:
        response = requests.get(pdf_url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return None

        with open("temp_sds.pdf", "wb") as f:
            f.write(response.content)

        doc = fitz.open("temp_sds.pdf")
        text = "\n".join(page.get_text() for page in doc)
        os.remove("temp_sds.pdf")

        hazard_codes = re.findall(r"H[2-4]\d{2}", text)
        section_13 = re.search(r"(?<=13[\.\s]*Disposal(?:\s+Considerations)?)(.*?)(?=\n\d{1,2}[\.\s]|$)", text, re.IGNORECASE | re.DOTALL)
        disposal_text = section_13.group(1).strip() if section_13 else "not found"

        return {
            "hazards": list(set(hazard_codes)) or ["not found"],
            "disposal": disposal_text,
            "sds_url": pdf_url,
            "source": "google_sds_scraper"
        }
    except Exception:
        return None

def save_to_firestore(product_name, data):
    product_doc = {
        "name": product_name,
        "hazards": data.get("hazards", ["not found"]),
        "disposal": data.get("disposal", "not found"),
        "sds_url": data.get("sds_url", ""),
        "source": data.get("source", "google_sds_scraper"),
        "image": "not found",
        "description": "not found",
        "score": "not found"
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

    pdf_url = search_google_sds(product_name)
    if not pdf_url:
        return jsonify({"error": "No SDS PDF found in Google results"}), 404

    data = extract_hazard_data_from_pdf(pdf_url)
    if not data:
        return jsonify({"error": "Failed to extract data from SDS PDF"}), 500

    save_to_firestore(product_name, data)
    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
