import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import quote

def scrape_chemical_safety(product_name):
    try:
        query = quote(product_name)
        url = f"https://www.chemicalsafety.com/sds-search/?q={query}"
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        result_link = soup.select_one("div.search-results a")
        if result_link:
            href = result_link.get("href")
            return {"source": "Chemical Safety", "sds_url": href}
    except Exception as e:
        print(f"❌ Chemical Safety error: {e}")
    return None

def scrape_screwfix(product_name):
    try:
        search_url = f"https://www.screwfix.com/search?search={quote(product_name)}"
        res = requests.get(search_url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        link = soup.select_one(".productDesc a")
        if link:
            return {"source": "Screwfix", "product_url": "https://www.screwfix.com" + link.get("href")}
    except Exception as e:
        print(f"❌ Screwfix error: {e}")
    return None

def scrape_google_sds(product_name):
    try:
        query = quote(f"{product_name} SDS filetype:pdf")
        google_url = f"https://www.google.com/search?q={query}"
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        res = requests.get(google_url, headers=headers, timeout=10)
        matches = re.findall(r"https://[^\s\"']+\.pdf", res.text)
        if matches:
            return {"source": "Google SDS", "sds_url": matches[0]}
    except Exception as e:
        print(f"❌ Google SDS error: {e}")
    return None

def scrape_product(product_name):
    print(f"🔍 Attempting to scrape SDS for: {product_name}")

    for scraper in [scrape_chemical_safety, scrape_screwfix, scrape_google_sds]:
        result = scraper(product_name)
        if result:
            print(f"✅ Found SDS from {result['source']}")
            return result

    print("❌ No SDS found after all fallbacks")
    return {"error": "No SDS found"}
