import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import quote
from firebase_utils import saveProductToFirestore

def scrape_chemical_safety(product_name):
    search_url = f"https://www.chemicalsafety.com/sds-search?q={quote(product_name)}"
    search_response = requests.get(search_url, timeout=10)
    if search_response.status_code != 200:
        return None

    soup = BeautifulSoup(search_response.text, "html.parser")
    product_links = soup.select(".sdsResultItem a")
    if not product_links:
        return None

    product_url = product_links[0]["href"]
    if not product_url.startswith("http"):
        product_url = "https://www.chemicalsafety.com" + product_url

    sds_response = requests.get(product_url, timeout=10)
    if sds_response.status_code != 200:
        return None

    sds_soup = BeautifulSoup(sds_response.text, "html.parser")

    # Extract product name
    name_elem = sds_soup.select_one("h1")
    product_name = name_elem.text.strip() if name_elem else product_name

    # Extract hazard codes
    hazards_section = sds_soup.find("h2", string=re.compile("Hazards Identification", re.IGNORECASE))
    h_codes = []
    if hazards_section:
        ul = hazards_section.find_next("ul")
        if ul:
            for li in ul.find_all("li"):
                matches = re.findall(r"(H\d{3})", li.text)
                h_codes.extend(matches)

    # Extract SDS URL
    pdf_link = sds_soup.find("a", href=re.compile(r"\.pdf"))
    sds_pdf_url = pdf_link["href"] if pdf_link else product_url

    # Build final product object
    product = {
        "name": product_name,
        "slug": product_name.lower().replace(" ", "-"),
        "source": product_url,
        "sds_url": sds_pdf_url,
        "hazards": h_codes or ["not found"],
        "image": False,
        "description": "not found",
        "score": 0,
        "score_raw": 0,
        "score_breakdown": {
            "health": 0,
            "environment": 0,
            "handling_disposal": 0
        },
        "disposal": "not found",
        "affiliate": False
    }

    saveProductToFirestore(product)
    return product
