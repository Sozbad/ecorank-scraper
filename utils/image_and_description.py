import requests
from bs4 import BeautifulSoup
import random
import time
from urllib.parse import quote

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X)...",
    "Mozilla/5.0 (iPhone; CPU iPhone OS)..."
]

def get_random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml",
        "Referer": "https://www.google.com/"
    }

def fetch_image_and_description(product_name):
    url = f"https://www.google.com/search?hl=en&tbm=shop&q={quote(product_name)}"
    resp = requests.get(url, headers=get_random_headers(), timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")

    img = soup.select_one("img[src^='http']")
    image_url = img["src"] if img else "not found"

    desc = "not found"
    for selector in [".sh-np__product-title", ".rgHvZc", ".BmP5tf", ".A2sOrd"]:
        tag = soup.select_one(selector)
        if tag:
            desc = tag.get_text().strip()
            break

    return {
        "image": image_url,
        "description": desc
    }
