import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
import re
from sds_parser import parse_sds_pdf

# Initialize Firebase
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
    if not hazard_codes:
        return "not found"
    if any(code.startswith("H2") for code in hazard_codes):
        return "Do not dispose in household waste. Take to a hazardous waste collection point or consult your council for flammable product disposal."
    elif any(code.startswith("H3") for code in hazard_codes):
        return "Use appropriate PPE and dispose through a licensed chemical waste provider."
    elif any(code.startswith("H4") for code in hazard_codes):
        return "Hazardous to aquatic life. Do not pour into drains. Use a chemical collection site."
    else:
        return "Dispose of contents and container in general waste only if permitted by local guidelines."

def build_product(name, description, hazard_codes, source, sds_url, disposal, data_quality):
    now = datetime.datetime.utcnow().isoformat() + "Z"
    if not hazard_codes:
        score = 0
        recommended = False
    else:
        score = max(0, 10 - len(hazard_codes))
        recommended = score >= 7

    return {
        "name": name or "not found",
        "description": description or "not found",
        "hazards": [],
        "hazard_codes": hazard_codes or [],
        "score": score,
        "recommended": recommended,
        "sds_url": sds_url or "not found",
        "source": source,
        "image": "not found",
        "barcode": "not found",
        "certifications": [],
        "categories": [],
        "primary_category": "not found",
        "subcategory": "not found",
        "health": None,
        "environment": None,
        "disposal": disposal,
        "last_scraped": now,
        "disclaimer": DISCLAIMER,
        "data_quality": data_quality
    }

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

        if not h_codes and detail_url and detail_url.endswith(".pdf"):
            print("📄 No hazards found, parsing SDS PDF...")
            parsed = parse_sds_pdf(detail_url)
            h_codes = parsed["hazard_codes"]
            disposal = parsed["disposal"]
            data_quality = parsed["data_quality"]
        else:
            disposal = assign_disposal_advice(h_codes)
            data_quality = "hazards found"

        print(f"✅ Found on Chemical Safety: {name}")
        return build_product(name, desc, h_codes, "Chemical Safety", detail_url, disposal, data_quality)
    except Exception as e:
        print(f"❌ Chemical Safety error: {e}")
        return None

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
        return build_product(name, "not found", [], "Screwfix", url, "not found", "limited")
    except Exception as e:
        print(f"❌ Screwfix error: {e}")
        return None

def scrape_amazon(product_name):
    try:
        print("🔍 Trying Amazon...")
        url = f"https://www.amazon.co.uk/s?k={product_name.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        title_element = soup.select_one("h2 span")
        if not title_element:
            print("❌ Amazon: No product found")
            return None
        title_text = title_element.text.strip()
        if (
            not title_text
            or "results for" in title_text.lower()
            or len(title_text) < 5
        ):
            print(f"❌ Amazon: Skipping generic match — {title_text}")
            return None
        print(f"✅ Found on Amazon: {title_text}")
        return build_product(title_text, "not found", [], "Amazon", url, "not found", "limited")
    except Exception as e:
        print(f"❌ Amazon error: {e}")
        return None

def scrape_product(product_name):
    cached = check_firestore_cache(product_name)
    if cached:
        return cached

    for scraper in [scrape_chemical_safety, scrape_screwfix, scrape_amazon]:
        result = scraper(product_name)
        if result:
            save_to_firestore(result)
            return result

    print("❌ All scrapers failed.")
    return {"error": "Product not found"}
