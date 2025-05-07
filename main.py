import os
import re
import requests
import fitz  # PyMuPDF
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import quote
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# Firebase init
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
db = firestore.client()
products_ref = db.collection("products")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# --- Search Google up to 3 pages for SDS PDFs
def search_google_sds(product_name):
    for page in range(0, 30, 10):  # 0, 10, 20 (3 pages)
        query = f"{product_name} SDS filetype:pdf"
        url = f"https://www.google.com/search?q={quote(query)}&start={page}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                match = re.search(r"/url\?q=(https?[^&]+)", href)
                if match:
                    pdf_url = match.group(1)
                    if pdf_url.endswith(".pdf"):
                        try:
                            head = requests.head(pdf_url, headers=HEADERS, allow_redirects=True, timeout=5)
                            if "application/pdf" in head.headers.get("Content-Type", ""):
                                return pdf_url
                        except:
                            continue
        except:
            continue
    return None

# --- PDF hazard extraction
def extract_hazards_disposal_from_pdf(pdf_url):
    try:
        res = requests.get(pdf_url, headers=HEADERS, timeout=15)
        with open("temp.pdf", "wb") as f:
            f.write(res.content)
        doc = fitz.open("temp.pdf")
        text = "\n".join([page.get_text() for page in doc])
        doc.close()
        os.remove("temp.pdf")

        hazard_codes = list(set(re.findall(r"H[2-4]\d{2}", text)))
        section_13 = re.search(r"(13\.*\s*DISPOSAL.*?)(?=\n\d+\.*|\Z)", text, re.DOTALL | re.IGNORECASE)
        disposal_text = section_13.group(1).strip() if section_13 else "not found"

        return {
            "hazards": hazard_codes or ["not found"],
            "disposal": disposal_text or "not found",
            "sds_url": pdf_url,
            "source": "google_sds_scraper"
        }
    except:
        return None

# --- HTML SDS fallback
def search_html_sds_page(product_name):
    query = f"{product_name} SDS site:chemicalsafety.com OR site:fisher.co.uk OR site:sigma-aldrich.com"
    url = f"https://www.google.com/search?q={quote(query)}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            match = re.search(r"/url\?q=(https?[^&]+)", href)
            if match:
                page_url = match.group(1)
                if "chemicalsafety" in page_url or "sds" in page_url.lower():
                    return page_url
    except:
        return None

# --- Google image + description fallback
def search_google_details(product_name):
    url = f"https://www.google.com/search?q={quote(product_name)}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        desc = ""
        image = ""

        for div in soup.find_all("div"):
            if div.get("data-attrid") == "wa:/description":
                desc = div.text.strip()
                break
        if not desc:
            snippet = soup.find("div", class_="BNeawe s3v9rd AP7Wnd")
            if snippet:
                desc = snippet.text.strip()

        img_tag = soup.find("img")
        if img_tag and "src" in img_tag.attrs:
            image = img_tag["src"]

        return {
            "description": desc or "not found",
            "image": image or "not found"
        }
    except:
        return {"description": "not found", "image": "not found"}

# --- Save to Firestore
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
    return "EcoRank scraper is running."

@app.route("/scrape", methods=["GET"])
def scrape():
    product_name = request.args.get("productName")
    if not product_name:
        return jsonify({"error": "Missing productName"}), 400

    existing = products_ref.document(product_name.lower()).get()
    if existing.exists:
        return jsonify(existing.to_dict())

    data = {}

    # Try PDF SDS
    pdf_url = search_google_sds(product_name)
    if pdf_url:
        data = extract_hazards_disposal_from_pdf(pdf_url)

    # Fallback to HTML SDS viewer
    if not data:
        html_url = search_html_sds_page(product_name)
        if html_url:
            data = {
                "hazards": ["not found"],
                "disposal": "not found",
                "sds_url": html_url,
                "source": "google_html_sds_fallback"
            }

    if not data:
        return jsonify({"error": "No SDS found in Google results"}), 404

    # Add image + description
    details = search_google_details(product_name)
    data.update(details)

    save_to_firestore(product_name, data)
    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
