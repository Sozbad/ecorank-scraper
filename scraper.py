import requests
from bs4 import BeautifulSoup
from firebase_admin import credentials, firestore, initialize_app
from sds_parser import parse_sds_pdf
import datetime
import os

# Firestore init
if not firestore._apps:
    cred = credentials.ApplicationDefault()
    initialize_app(cred)
db = firestore.client()

def scrape_product(product_name):
    query = f"{product_name} SDS filetype:pdf"
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        for a in soup.select("a"):
            href = a.get("href")
            if href and "pdf" in href and "http" in href:
                pdf_url = href.split("q=")[-1].split("&")[0]
                print(f"🔗 Found SDS PDF: {pdf_url}")
                pdf_bytes = requests.get(pdf_url).content
                with open("/tmp/temp.pdf", "wb") as f:
                    f.write(pdf_bytes)
                sds_text = parse_sds_pdf("/tmp/temp.pdf") or ""

                product_data = {
                    "name": product_name,
                    "description": "SDS fallback scrape",
                    "image": "",
                    "sds_url": pdf_url,
                    "hazards": [],
                    "hazard_codes": [],
                    "health": 0,
                    "environment": 0,
                    "disposal": 0,
                    "score": 10,
                    "recommended": True,
                    "primary_category": "Uncategorized",
                    "subcategory": "Fallback",
                    "categories": ["Uncategorized"],
                    "barcode": "",
                    "certifications": [],
                    "last_scraped": datetime.datetime.utcnow().isoformat() + "Z",
                    "source": "google-fallback"
                }

                doc_id = product_name.lower().replace(" ", "-")
                db.collection("products").document(doc_id).set(product_data)
                print("✅ Saved to Firestore:", doc_id)
                return product_data

        return {"error": "No SDS PDF found"}
    except Exception as e:
        print(f"❌ Scraping failed: {e}")
        return {"error": str(e)}
