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

# Search Google for PDF or HTML SDS links
def search_google_sds(product_name, max_pages=3):
    for page in range(0, max_pages):
        start = page * 10
        query = f"{product_name} SDS filetype:pdf"
        url = f"https://www.google.com/search?q={quote(query)}&start={start}"
        r = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            match = re.search(r"/url\?q=(https?[^&]+)", href)
            if match:
                link = match.group(1)
                # Accept PDF links
                if link.lower().endswith(".pdf"):
                    try:
                        head = requests.head(link, headers=HEADERS, allow_redirects=True, timeout=5)
                        if "application/pdf" in head.headers.get("Content-Type", ""):
                            return {"type": "pdf", "url": link}
                    except:
                        continue
                # Accept HTML viewer pages
                elif any(domain in link for domain in ["chemicalsafety.com", "fisher.co.uk", "sigma-aldrich.com"]):
                    return {"type": "html", "url": link}
    return None

# Extract hazard data from PDF
def extract_hazards_disposal_from_pdf(pdf_url):
    try:
        res = requests.get(pdf_url, headers=HEADERS)
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
        }
    except:
        return {
            "hazards": ["not found"],
            "disposal": "not found"
        }

# Fallback for image and description
def search_google_details(product_name):
    try:
        url = f"https://www.google.com/search?q={quote(product_name)}"
        r = requests.get(url, headers=HEADERS)
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

# Save to Firestore
def save_to_firestore(product_name, data):
    record = {
        "name": product_name,
        "hazards": data.get("hazards", ["not found"]),
        "disposal": data.get("disposal", "not found"),
        "sds_url": data.get("sds_url", ""),
        "source": data.get("source", ""),
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
def health_check():
    return "EcoRank scraper is running."

@app.route("/scrape", methods=["GET"])
def scrape():
    product_name = request.args.get("productName")
    if not product_name:
        return jsonify({"error": "Missing productName"}), 400

    existing = products_ref.document(product_name.lower()).get()
    if existing.exists:
        return jsonify(existing.to_dict())

    result = search_google_sds(product_name)

    if not result:
        return jsonify({"error": "No SDS found in Google results"}), 404

    if result["type"] == "pdf":
        data = extract_hazards_disposal_from_pdf(result["url"])
        data["sds_url"] = result["url"]
        data["source"] = "google_pdf_sds"
    else:
        data = {
            "hazards": ["not found"],
            "disposal": "not found",
            "sds_url": result["url"],
            "source": "google_html_sds"
        }

    details = search_google_details(product_name)
    data.update(details)
    save_to_firestore(product_name, data)
    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
