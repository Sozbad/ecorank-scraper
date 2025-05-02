import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
import re

# Initialize Firebase if not already
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
db = firestore.client()

DISCLAIMER = (
    "The information contained herein is based on data compiled from the chemical components "
    "of the (M)SDS and may not accurately represent the safety hazards for the product. "
    "Only the manufacturer of the product can make actual representations about the hazard profile. "
    "No warranty is expressed or implied regarding the accuracy of these data."
)

def assign_disposal_advice(hazard_codes):
    if any(code.startswith("H2") for code in hazard_codes):
        return "Do not dispose in household waste. Take to a hazardous waste collection point or consult your council for flammable product disposal."
    elif any(code.startswith("H3") for code in hazard_codes):
        return "Use appropriate PPE and dispose through a licensed chemical waste provider."
    elif any(code.startswith("H4") for code in hazard_codes):
        return "Hazardous to aquatic life. Do not pour into drains. Use a chemical collection site."
    else:
        return "Dispose of contents and container in general waste only if permitted by local guidelines."

def build_product(name, description, hazard_codes, source, sds_url):
    score = max(0, 10 - len(hazard_codes))
    now = datetime.datetime.utcnow().isoformat() + "Z"
    return {
        "name": name,
        "description": description,
        "hazards": [],  # Can be enhanced later
        "hazard_codes": hazard_codes,
        "score": score,
        "recommended": score >= 7,
        "sds_url": sds_url,
        "source": source,
        "image": "",
        "barcode": "",
        "certifications": [],
        "categories": [],
        "primary_category": "",
        "subcategory": "",
        "health": None,
        "environment": None,
        "disposal": assign_disposal_advice(hazard_codes),
        "last_scraped": now,
        "disclaimer": DISCLAIMER
    }

# Check Firestore cache first
def check_firestore_cache(product_name):
    docs = db.collection("products").where("name", "==", product_name).stream()
    for doc in docs:
        print(f"📦 Cache hit for '{product_name}'")
        return doc.to_dict()
    print(f"🕵️ Cache miss for '{product_name}'")
    return None

def save_to_firestore(product):
    db.collection("products").add(product)
    print(f"✅ Saved to Firestore: {product['name']}")

# Chemical Safety Scraper
def scrape_chemical_safety(product_name):
    try:
        print("🔍 Trying Chemical Safety...")
        url = f"https://www.chemical-safety.com/sds-search/?q={product_name.replace(' ', '+')}"
        res = requests.get(url, verify=False, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        table_row = soup.select_one("table tbody tr")
        if not table_row:
            print("❌ Chemical Safety: No results")
            return None
        link = table_row.find("a", href=True)
        detail_url = link['href'] if link else None
        detail_res = requests.get(detail_url, verify=False, timeout=10)
        detail_soup = BeautifulSoup(detail_res.text, "html.parser")
        text = detail_soup.get_text()
        h_codes = list(set(re.findall(r"H\d{3}", text)))
        name = detail_soup.find("h1").get_text(strip=True) if detail_soup.find("h1") else product_name
        desc = detail_soup.find("p").get_text(strip=True) if detail_soup.find("p") else ""
        print(f"✅ Found on Chemical Safety: {name}")
        return build_product(name, desc, h_codes, "Chemical Safety", detail_url)
    except Exception as e:
        print(f"❌ Chemical Safety error: {e}")
        return None

# Screwfix fallback
def scrape_screwfix(product_name):
    try:
        print("🔍 Trying Screwfix...")
        url = f"https://www.screwfix.com/search?search={product_name.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        first = soup.select_one(".SearchResults .productBox .productDescription")
        if not first:
            print("❌ Screwfix: No match")
            return None
        name = first.text.strip()
        print(f"✅ Found on Screwfix: {name}")
        return build_product(name, "", [], "Screwfix", url)
    except Exception as e:
        print(f"❌ Screwfix error: {e}")
        return None

# Amazon fallback
def scrape_amazon(product_name):
    try:
        print("🔍 Trying Amazon...")
        url = f"https://www.amazon.co.uk/s?k={product_name.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        title = soup.select_one("h2 span")
        if not title:
            print("❌ Amazon: No match")
            return None
        name = title.text.strip()
        print(f"✅ Found on Amazon: {name}")
        return build_product(name, "", [], "Amazon", url)
    except Exception as e:
        print(f"❌ Amazon error: {e}")
        return None

# Entry point
def scrape_product(product_name):
    # Step 1: Cache
    cached = check_firestore_cache(product_name)
    if cached:
        return cached

    # Step 2: Scrapers
    for scraper in [scrape_chemical_safety, scrape_screwfix, scrape_amazon]:
        result = scraper(product_name)
        if result:
            save_to_firestore(result)
            return result

    print("❌ All scrapers failed.")
    return {"error": "Product not found"}
