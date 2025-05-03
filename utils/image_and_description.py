import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
}

def fetch_image_and_description(product_name):
    query = f"{product_name}"
    url = f"https://www.google.com/search?hl=en&tbm=shop&q={requests.utils.quote(query)}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        img = soup.select_one("img")
        img_url = img["src"] if img and "src" in img.attrs else "not found"

        desc_tag = soup.select_one("div,span")
        description = desc_tag.get_text().strip() if desc_tag else "not found"

        return {
            "image": img_url,
            "description": description
        }

    except Exception:
        return {
            "image": "not found",
            "description": "not found"
        }
