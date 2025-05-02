import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
import re
from sds_parser import parse_sds_pdf
from google_sds_fallback import google_sds_fallback

if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
db = firestore.client()

def assign_disposal(h_codes):
    if not h_codes:
        return "not found"
    if any(code.startswith("H2") for code in h_codes):
        return "Do not dispose in household waste. Take to a hazardous waste collection site."
    elif any(code.startswith("H3") for code in h_codes):
        return "Use PPE and dispose through a licensed provider."
    elif any(code.startswith("H4") for code in h_codes):
        return "Hazardous to environment. Never pour into drains."
    return "Dispose of according to local regulations."

def check_firestore_cache(product_name):
    docs = db.collection("products").where("name", "==", product_name).stream()
    for doc in docs:
        print(f"📦 Cache hit for '{product_name}'")
        return doc.to_dict()
    return None

def save_to_firestore(product):
    db.collection("products").add(product)
    print(f"✅ Saved: {product['name']}")

def build_product(product_name, meta, fallback_data=None):
    now = datetime.datetime.utcnow().isoformat() + "Z"
    hazards = fallback_data["hazard_codes"] if fallback_data else []
    disposal = fallback_data["disposal"] if fallback_data else "not found"
    score = max(0, 10 - len(hazards)) if hazards else 10
    recommended = score >= 7 and bool(hazards)

    return {
        "name": product_name,
        "description": meta.get("description", "not found"),
        "image": meta.get("image", "not found"),
        "hazards": [],
        "hazard_codes": hazards,
        "score": score,
        "recommended": recommended,
        "barcode": "not found",
        "categories": [],
        "primary_category": "not found",
        "subcategory": "not found",
        "certifications": [],
        "health": None,
        "environment": None,
        "disposal": disposal,
        "sds_url": fallback_data["sds_url"] if fallback_data else "not found",
        "source": fallback_data["source"] if fallback_data else "unknown",
        "data_quality": fallback_data["data_quality"] if fallback_data else "unknown",
        "last_scraped": now,
        "disclaimer": "SDS data is parsed from public sources. Accuracy is not guaranteed."
    }

def get_fallback_meta(product_name):
    try:
        url = f"https://www.amazon.co.uk/s?k={product_name.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        first = soup.select_one("h2 span")
        return {
            "description": first.text.strip() if first else "not found",
            "image": "not found"
        }
    except:
        return {"description": "not found", "image": "not found"}

def scrape_product(product_name):
    cached = check_firestore_cache(product_name)
    if cached:
        return cached

    # Try main SDS fallback
    sds_data = google_sds_fallback(product_name)

    if not sds_data:
        print("❌ SDS fallback failed. Skipping.")
        return {"error": "Product not found"}

    # Fill in any missing fields
    meta = get_fallback_meta(product_name)
    final_product = build_product(product_name, meta, sds_data)
    save_to_firestore(final_product)
    return final_product
