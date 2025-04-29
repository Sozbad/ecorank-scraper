import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
import re
import time

# Initialize Firestore
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Disclaimer
DISCLAIMER = (
    "The information contained herein is based on data compiled from the chemical components "
    "of the (M)SDS and may not accurately represent the safety hazards for the product. "
    "Only the manufacturer of the product can make actual representations about the hazard profile. "
    "No warranty is expressed or implied regarding the accuracy of these data."
)

# Common structure
def build_product(name, description, hazards, hazard_codes, source, sds_url=""):
    score = max(0, 10 - len(hazard_codes))  # Example scoring logic
    now = datetime.datetime.utcnow().isoformat() + "Z"
    return {
        "name": name,
        "description": description,
        "hazards": hazards,
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
        "disposal": None,
        "last_scraped": now,
        "disclaimer": DISCLAIMER,
    }

# Scraper 1: Chemical Safety
def scrape_chemical_safety(product_name):
    try:
        url = f"https://www.chemical-safety.com/sds-search/?q={product_name.replace(' ', '+')}"
        res = requests.get(url, verify=False, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        result = soup.select_one("table tbody tr")
        if not result:
            return None
        link = result.find("a")["href"]
        detail_res = requests.get(link, verify=False, timeout=10)
        detail = BeautifulSoup(detail_res.text, "html.parser")
        text = detail.get_text()
        hazard_codes = re.findall(r"H\d{3}", text)
        name = detail.find("h1").get_text(strip=True) if detail.find("h1") else product_name
        desc = detail.find("p").get_text(strip=True) if detail.find("p") else ""
        return build_product(name, desc, [], list(set(hazard_codes)), "Chemical Safety", link)
    except Exception:
        return None

# Scraper 2: Fisher Scientific
def scrape_fisher(product_name):
    try:
        search_url = f"https://www.fishersci.com/shop/products/{product_name.replace(' ', '-')}/"
        res = requests.get(search_url, timeout=10)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text()
        hazard_codes = re.findall(r"H\d{3}", text)
        name = soup.find("title").text.strip()
        return build_product(name, "", [], list(set(hazard_codes)), "Fisher Scientific", search_url)
    except Exception:
        return None

# Scraper 3: Sigma-Aldrich
def scrape_sigma(product_name):
    try:
        search_url = f"https://www.sigmaaldrich.com/US/en/search/{product_name.replace(' ', '%20')}"
        res = requests.get(search_url, timeout=10)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, "html.parser")
        first_link = soup.select_one("a.search-result__product-link")
        if not first_link:
            return None
        detail_url = "https://www.sigmaaldrich.com" + first_link["href"]
        detail_res = requests.get(detail_url, timeout=10)
        detail = BeautifulSoup(detail_res.text, "html.parser")
        text = detail.get_text()
        hazard_codes = re.findall(r"H\d{3}", text)
        name = detail.find("h1").get_text(strip=True) if detail.find("h1") else product_name
        return build_product(name, "", [], list(set(hazard_codes)), "Sigma-Aldrich", detail_url)
    except Exception:
        return None

# Scraper 4: Screwfix
def scrape_screwfix(product_name):
    try:
        url = f"https://www.screwfix.com/search?search={product_name.replace(' ', '+')}"
        res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        first = soup.select_one(".SearchResults .productBox")
        if not first:
            return None
        name = first.select_one(".productDescription").text.strip()
        desc = first.select_one(".productDescription").text.strip()
        return build_product(name, desc, [], [], "Screwfix", url)
    except Exception:
        return None

# Scraper 5: Toolstation
def scrape_toolstation(product_name):
    try:
        url = f"https://www.toolstation.com/search?searchterm={product_name.replace(' ', '+')}"
        res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        first = soup.select_one(".productgrid .product-title")
        if not first:
            return None
        name = first.text.strip()
        return build_product(name, "", [], [], "Toolstation", url)
    except Exception:
        return None

# Scraper 6: Amazon (basic fallback)
def scrape_amazon(product_name):
    try:
        url = f"https://www.amazon.co.uk/s?k={product_name.replace(' ', '+')}"
        res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        title = soup.select_one("h2 span")
        if not title:
            return None
        name = title.text.strip()
        return build_product(name, "", [], [], "Amazon", url)
    except Exception:
        return None

# Main fallback function
def scrape_product(product_name):
    fallback_order = [
        scrape_chemical_safety,
        scrape_fisher,
        scrape_sigma,
        scrape_screwfix,
        scrape_toolstation,
        scrape_amazon,
    ]
    for scraper in fallback_order:
        try:
            result = scraper(product_name)
            if result:
                db.collection("products").add(result)
                return result
        except Exception:
            continue
    return None
