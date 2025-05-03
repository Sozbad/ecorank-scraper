import requests
from bs4 import BeautifulSoup
from sds_parser import parse_sds_pdf

def scrape_product(product_name):
    try:
        # Google-style PDF search (simple fallback logic)
        query = f"{product_name} SDS filetype:pdf"
        google_search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        resp = requests.get(google_search_url, headers=headers)
        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.select("a")

        for link in links:
            href = link.get("href")
            if href and "pdf" in href and "http" in href:
                pdf_url = href.split("q=")[-1].split("&")[0]
                print(f"🔗 Found SDS PDF: {pdf_url}")
                pdf_resp = requests.get(pdf_url)
                with open("/tmp/temp.pdf", "wb") as f:
                    f.write(pdf_resp.content)

                text = parse_sds_pdf("/tmp/temp.pdf")
                return {
                    "productName": product_name,
                    "sds_text_snippet": text[:1000],
                    "sds_url": pdf_url
                }

        return {"error": "No SDS PDF found"}
    except Exception as e:
        return {"error": str(e)}
