import requests
from bs4 import BeautifulSoup

def scrape_product(product_name):
    try:
        query = f"{product_name} SDS site:chemicalsafety.com"
        url = f"https://www.google.com/search?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers)

        soup = BeautifulSoup(res.text, "html.parser")
        links = soup.select("a")
        sds_url = None
        for link in links:
            href = link.get("href", "")
            if "chemicalsafety.com/sds/" in href:
                sds_url = href.split("&")[0].replace("/url?q=", "")
                break

        if not sds_url:
            return {"error": "No SDS found"}

        sds_res = requests.get(sds_url, headers=headers)
        sds_soup = BeautifulSoup(sds_res.text, "html.parser")

        title_tag = sds_soup.find("h1")
        title = title_tag.text.strip() if title_tag else "Untitled"

        h_section = sds_soup.find("section", class_="hazards")
        hazards = h_section.get_text(strip=True) if h_section else "Hazard info not found"

        return {
            "product": product_name,
            "title": title,
            "hazards": hazards,
            "source": sds_url
        }
    except Exception as e:
        return {"error": str(e)}
