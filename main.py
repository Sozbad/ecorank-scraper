import os
import re
import requests
import fitz  # PyMuPDF
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from firebase_admin import credentials, firestore, initialize_app
from urllib.parse import quote

app = Flask(__name__)

# Firebase setup
import firebase_admin
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
db = firestore.client()
products_ref = db.collection('products')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def fetch_google_results(product_name, num_pages=2):
    query = f"{product_name} SDS"
    results = []
    for page in range(num_pages):
        start = page * 10
        url = f"https://www.google.com/search?q={quote(query)}&start={start}"
        r = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a['href']
            match = re.search(r"/url\?q=(https?[^&]+)", href)
            if match:
                link = match.group(1)
                if "pdf" in link.lower() or "sdsviewer" in link.lower() or "safety-data" in link.lower():
                    results.append(link)
    return results

def extract_pdf_data(pdf_url):
    try:
        r = requests.get(pdf_url, headers=HEADERS)
        if 'application/pdf' not in r.headers.get('Content-Type', ''):
            return None
        with open("temp.pdf", "wb") as f:
            f.write(r.content)
        doc = fitz.open("temp.pdf")
        text = "\n".join(page.get_text() for page in doc)
        os.remove("temp.pdf")
        hazard_codes = list(set(re.findall(r"H[2-4]\d{2}", text)))
        disposal_match = re.search(r"(Section\s*13.*?)(Section\s*\d+|$)", text, re.IGNORECASE | re.DOTALL)
        disposal = disposal_match.group(1).strip() if disposal_match else "not found"
        return {"hazards": hazard_codes or ["not found"], "disposal": disposal}
    except Exception as e:
        print(f"⚠️ PDF parse error: {e}")
        return None

def extract_html_sds_data(url):
    try:
        r = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n")
        hazard_codes = list(set(re.findall(r"H[2-4]\d{2}", text)))
        disposal_match = re.search(r"(Section\s*13.*?)(Section\s*\d+|$)", text, re.IGNORECASE | re.DOTALL)
        disposal = disposal_match.group(1).strip() if disposal_match else "not found"
        return {"hazards": hazard_codes or ["not found"], "disposal": disposal}
    except Exception as e:
        print(f"⚠️ HTML SDS parse error: {e}")
        return None

def scrape_metadata(product_name):
    try:
        url = f"https://www.amazon.co.uk/s?k={quote(product_name)}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        desc = soup.select_one("h2 span")
        img = soup.select_one("img.s-image")
        return {
            "description": desc.text.strip() if desc else "not found",
            "image": img['src'] if img and img.has_attr('src') else "not found"
        }
    except:
        return {"description": "not found", "image": "not found"}

def save_to_firestore(name, hazards, disposal, sds_url, image, description, source):
    missing = not all([hazards and hazards != ["not found"], disposal != "not found", image != "not found", description != "not found"])
    doc = {
        "name": name,
        "hazards": hazards,
        "disposal": disposal,
        "sds_url": sds_url,
        "source": source,
        "image": image,
        "description": description,
        "missingFields": missing
    }
    products_ref.document(name.lower()).set(doc)

@app.route("/")
def health():
    return "✅ EcoRank fallback scraper is live."

@app.route("/scrape", methods=["GET"])
def scrape():
    name = request.args.get("productName")
    if not name:
        return jsonify({"error": "Missing productName"}), 400

    cached = products_ref.document(name.lower()).get()
    if cached.exists:
        return jsonify(cached.to_dict())

    links = fetch_google_results(name)
    for link in links:
        print(f"🔎 Trying: {link}")
        if link.lower().endswith(".pdf"):
            parsed = extract_pdf_data(link)
        else:
            parsed = extract_html_sds_data(link)
        if parsed and parsed.get("hazards"):
            meta = scrape_metadata(name)
            save_to_firestore(name, parsed["hazards"], parsed["disposal"], link, meta["image"], meta["description"], link)
            return jsonify({
                "name": name,
                "hazards": parsed["hazards"],
                "disposal": parsed["disposal"],
                "sds_url": link,
                "image": meta["image"],
                "description": meta["description"]
            })

    return jsonify({"error": "No SDS found in Google results"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
