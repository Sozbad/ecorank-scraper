import requests
from bs4 import BeautifulSoup

def get_image_and_description(query):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://www.google.com/search?tbm=shop&q={query}"
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        img = soup.find("img")
        image = img["src"] if img else None

        desc = soup.find("div", attrs={"class": "sh-ds__full-txt"})
        description = desc.text.strip() if desc else None

        return image, description
    except:
        return None, None
