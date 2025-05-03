import firebase_admin
from firebase_admin import credentials, firestore
import datetime
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
        return doc.to_dict()
    return None

def save_to_firestore(product):
    try:
        slug = product["name"].lower().replace(" ", "-")
        product["slug"] = slug
        product["timestamp"] = datetime.datetime.utcnow().isoformat()
        db.collection("products").document(slug).set(product)
        print(f"✅ Saved product to Firestore: {slug}")
    except Exception as e:
        print(f"❌ Firestore save failed: {e}")

def scrape_product(product_name):
    product_name = product_name.strip()
    print(f"🔍 Scraping for: {product_name}")

    cached = check_firestore_cache(product_name)
    if cached:
        print("⚡ Found in Firestore cache")
        return cached

    print("🌐 Trying Google SDS fallback...")
    fallback = google_sds_fallback(product_name)

    if fallback:
        h_codes = fallback.get("hazard_codes", [])
        fallback["disposal"] = assign_disposal(h_codes)
        fallback["name"] = product_name
        save_to_firestore(fallback)
        return fallback

    print("❌ No SDS found for this product.")
    return {"error": "No SDS found"}
