import os
import re
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
from googlesearch import search
from PyPDF2 import PdfReader
from openai import OpenAI
from utils.image_and_description import get_image_and_description
from utils.hazard_phrase_map import map_phrase_to_hcode

# Init Firebase
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
db = firestore.client()

openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_sds_data(url):
    text = ""
    if url.endswith(".pdf"):
        response = requests.get(url)
        with open("temp_sds.pdf", "wb") as f:
            f.write(response.content)
        reader = PdfReader("temp_sds.pdf")
        for page in reader.pages:
            text += page.extract_text()
    else:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(separator="\n")

    hazard_lines = re.findall(r"(Causes.*|May cause.*|Fatal.*|H\d{3})", text, re.IGNORECASE)
    hazards = list(set([map_phrase_to_hcode(line) for line in hazard_lines if map_phrase_to_hcode(line)]))

    disposal_match = re.search(r"(Section\s*13[\s\S]{0,300})", text, re.IGNORECASE)
    disposal = disposal_match.group(1).strip() if disposal_match else "not found"
    return hazards, disposal, text

def get_gpt_swaps(name, hazard_list):
    prompt = f"""You are EcoRank, an expert in product safety and environmental impact.
The product "{name}" has these hazard codes: {', '.join(hazard_list)}.

Suggest 2–3 safer commercial alternatives that:
- Serve the same function
- Have fewer or no hazard codes
- Are real products from known brands
- Prefer those with eco-certifications if known

Only return product names, not explanations."""
    try:
        resp = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        lines = resp.choices[0].message.content.strip().splitlines()
        return [line.strip("-• ") for line in lines if len(line.strip()) > 2]
    except:
        return []

def handle_search(product_name):
    doc_id = product_name.lower()
    doc_ref = db.collection("products").document(doc_id)
    if doc_ref.get().exists:
        return {"status": "exists", "message": "Already in database"}

    urls = list(search(f"{product_name} SDS filetype:pdf", num_results=20))
    sds_url = next((u for u in urls if "sds" in u.lower()), None)

    hazards, disposal, raw_text = [], "not found", ""
    source = "GPT estimate"
    if sds_url:
        try:
            hazards, disposal, raw_text = extract_sds_data(sds_url)
            if hazards or disposal != "not found":
                source = "Verified SDS"
        except:
            pass

    if not hazards:
        hazards += re.findall(r"H\d{3}", raw_text)

    image, description = get_image_and_description(product_name)
    swaps = get_gpt_swaps(product_name, hazards)

    doc_ref.set({
        "name": product_name,
        "hazards": hazards if hazards else ["not found"],
        "disposal": disposal,
        "description": description or "not found",
        "image": image or "/icons/placeholder.svg",
        "sds_url": sds_url or "not found",
        "swaps": swaps,
        "missingFields": len(hazards) == 0 or disposal == "not found",
        "source": source,
        "verified": source == "Verified SDS"
    })

    return {
        "status": "done",
        "hazards": hazards,
        "disposal": disposal,
        "swaps": swaps,
        "image": image,
        "source": source
    }
