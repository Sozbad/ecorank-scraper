import re
import requests
from bs4 import BeautifulSoup
from firebase_admin import firestore

from utils.google_sds_fallback import search_google_for_sds_pdf, extract_sds_data_from_pdf

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
}

db = firestore.client()
products_ref = db.collection("products")


def scrape_amazon(product_name):
    try:
        url = f"https://www.amazon.co.uk/s?k={requests.utils.quote(product_name)}"
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        product = soup.select_one(".s-result-item h2 a")
        if not product:
            return {}

        product_url = "https://www.amazon.co.uk" + product["href"]
        product_res = requests.get(product_url, headers=HEADERS, timeout=10)
        detail_soup = BeautifulSoup(product_res.text, "html.parser")

        title = detail_soup.select_one("#productTitle")
        img = detail_soup.select_one("#imgTagWrapperId img")

        return {
            "description": title.text.strip() if title else "not found",
            "image": img["src"] if img else "not found"
        }
    except Exception:
        return {}


def scrape_screwfix(product_name):
    try:
        url = f"https://www.screwfix.com/search?search={requests.utils.quote(product_name)}"
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        product = soup.select_one(".productDesc a")
        if not product:
            return {}

        product_url = "https://www.screwfix.com" + product["href"]
        product_res = requests.get(product_url, headers=HEADERS, timeout=10)
        detail_soup = BeautifulSoup(product_res.text, "html.parser")

        title = detail_soup.select_one("h1")
        img = detail_soup.select_one(".js-imgZoom")

        return {
            "description": title.text.strip() if title else "not found",
            "image": img["src"] if img else "not found"
        }
    except Exception:
        return {}


def get_product_data(product_name):
    product_doc = {
        "name": product_name,
        "hazards": ["not found"],
        "disposal": "not found",
        "description": "not found",
        "image": "not found",
        "score": "not found",
        "sds_url": "",
        "source": ""
    }

    # Step 1: Google SDS fallback
    pdf_url = search_google_for_sds_pdf(product_name)
    if pdf_url:
        sds_data = extract_sds_data_from_pdf(pdf_url)
        if sds_data:
            product_doc.update(sds_data)

    # Step 2: Try Screwfix
    screwfix_data = scrape_screwfix(product_name)
    for k in ["image", "description"]:
        if screwfix_data.get(k) and product_doc[k] == "not found":
            product_doc[k] = screwfix_data[k]

    # Step 3: Try Amazon
    amazon_data = scrape_amazon(product_name)
    for k in ["image", "description"]:
        if amazon_data.get(k) and product_doc[k] == "not found":
            product_doc[k] = amazon_data[k]

    # Final save
    products_ref.document(product_name.lower()).set(product_doc)
    return product_doc
