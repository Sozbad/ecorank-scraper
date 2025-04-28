# scraper.py
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
import datetime

# Firestore init
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Hazard to score mappings
hazard_mapping = {
    "flammable": {"health": 1, "environment": 0, "disposal": 1},
    "toxic": {"health": 3, "environment": 2, "disposal": 2},
    "corrosive": {"health": 2, "environment": 1, "disposal": 2},
    "environment": {"health": 0, "environment": 3, "disposal": 2},
    "health hazard": {"health": 3, "environment": 1, "disposal": 1}
}

# Category mapping
category_keywords = {
    "lubricant": ("Lubricants", "Multi-Purpose Lubricants"),
    "bike": ("Lubricants", "Bicycle Chain Lubricants"),
    "coolant": ("Car Care", "Coolants"),
    "paint": ("Paints", "Spray Paints"),
    "de-icer": ("Car Care", "De-Icers"),
    "cleaner": ("Cleaning Products", "Surface Cleaners"),
    "graffiti remover": ("Cleaning Products", "Graffiti Remover"),
    "wood stain": ("Wood Treatments", "Exterior Wood Stain"),
    "varnish": ("Wood Treatments", "Wood Varnishes"),
    "adhesive": ("Glues & Adhesives", "Multi-Purpose Adhesives"),
    "sanitiser": ("Cleaning Products", "Sanitisers"),
}

def score_product(hazards):
    base_score = 10.0
    health = environment = disposal = 0

    for hazard in hazards:
        hazard = hazard.lower()
        mapping = hazard_mapping.get(hazard)
        if mapping:
            health += mapping["health"]
            environment += mapping["environment"]
            disposal += mapping["disposal"]

    score = base_score - (0.5 * health) - (0.5 * environment) - (0.5 * disposal)
    score = max(0.0, round(score, 1))
    return score, health, environment, disposal

def assign_categories(product_name, description):
    text = (product_name + " " + description).lower()
    for keyword, (primary, sub) in category_keywords.items():
        if keyword in text:
            return primary, sub
    return "Other", "General Purpose"

def scrape_product(product_name):
    search_url = f"https://www.chemical-safety.com/sds-search/?q={product_name.replace(' ', '+')}"
    response = requests.get(search_url)
    if response.status_code != 200:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    first_result = soup.find("div", class_="product-listing")

    if not first_result:
        return None

    title = first_result.find("h2").get_text(strip=True)
    description = first_result.find("p").get_text(strip=True) if first_result.find("p") else ""
    sds_link_tag = first_result.find("a", href=True)
    sds_url = sds_link_tag['href'] if sds_link_tag else ""

    # Fake hazard extraction (Chemical Safety sometimes doesn't show on listing)
    # You would scrape inside SDS if needed - here we assume a set for now
    hazards = ["Flammable", "Health Hazard", "Environment"]

    score, health, environment, disposal = score_product(hazards)
    recommended = score >= 7.0
    primary_category, subcategory = assign_categories(product_name, description)

    now = datetime.datetime.utcnow().isoformat() + "Z"

    product_data = {
        "name": title,
        "description": description,
        "image": "",  # Optional to scrape later
        "sds_url": sds_url,
        "hazards": hazards,
        "hazard_codes": [],
        "health": health,
        "environment": environment,
        "disposal": disposal,
        "score": score,
        "recommended": recommended,
        "primary_category": primary_category,
        "subcategory": subcategory,
        "categories": [primary_category],
        "barcode": "",
        "certifications": [],
        "last_scraped": now
    }

    # Upload to Firestore
    db.collection("products").add(product_data)
    return product_data
