import os
import re
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
from PyPDF2 import PdfReader
from openai import OpenAI
from utils.image_and_description import get_image_and_description
from utils.hazard_phrase_map import map_phrase_to_hcode

# Init Firebase
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Init GPT API
openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Helper: extract hazard + disposal from SDS page ---
def extract_sds_data(sds_url):
    text = ""
    try:
        if sds_url.endswith(".pdf"):
            response = requests.get(sds_url)
            with open("temp_sds.pdf", "wb") as f:
                f.write(response.content)
            reader = PdfReader("temp_sds.pdf")
            for page in reader.pages:
                text += page.extract_text()
        else:
            response = requests.get(sds_url)
            soup = BeautifulSoup(response.text, "html.parser")
            text = soup.get_text(separator="\n")
    except Exception:
        return [], "not found", ""

    hazard_lines = re.findall(r"(Causes.*|May cause.*|Fatal.*|H\d{3})", text, re.IGNORECASE)
    hazards = list(set([map_phrase_to_hcode(line) for line in hazard_lines if map_phrase_to_hcode(line)]))

    disposal_match = re.search(r"(Section\s*13[\s\S]{0,300})", text, re.IGNORECASE)
    disposal = disposal_match.group(1).strip() if disposal_match else "not found"
    return hazards, disposal, text

# --- GPT to find real SDS URL ---
def get_sds_link_via_gpt(product_name):
    prompt = f"""Find the most reliable public SDS (Safety Data Sheet) link for the following product:
Product: "{product_name}"

Please return ONLY the direct URL to the SDS file — PDF or SDS viewer page — with no extra commentary."""
    try:
        resp = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        url = re.search(r"(https?://[^\s]+)", resp.choices[0].message.content.strip())
        return url.group(1) if url else None
    except Exception:
        return None

# --- GPT: suggest greener swaps ---
def get_gpt_swaps(name, hazard_list):
    if not hazard_list:
        return []
    prompt = f"""The product "{name}" has hazard codes: {', '.join(hazard_list)}.

Suggest 2–3 greener, safer commercial alternatives that:
- Serve the same function
- Have fewer or no hazard codes
- Are real products from known brands
- Prefer eco-certified products if possible

Only return product names, no explanation."""
    try:
        resp = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        lines = resp.choices[0].message.content.strip().splitlines()
        return [line.strip("-• ") for line in lines if len(line.strip()) > 2]
    except Exception:
        return []

# --- Main handler ---
def handle_search(product_name):
    doc_id = product_name.lower()
    doc_ref = db.collection("products").document(doc_id)
    if doc_ref.get().exists:
        return {"status": "exists", "message": "Already in database"}

    sds_url = get_sds_link_via_gpt(product_name)
    hazards, disposal, raw_text = [], "not found", ""
    source = "GPT estimate"

    if sds_url:
        hazards, disposal, raw_text = extract_sds_data(sds_url)
        if hazards or disposal != "not found":
            source = "Verified SDS"

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
        "missingFields": [k for k in ["hazards", "disposal", "description", "image"] if eval(k) in ([], "not found", None)],
        "source": source,
        "verified": source == "Verified SDS"
    })

    return {
        "status": "done",
        "hazards": hazards,
        "disposal": disposal,
        "swaps": swaps,
        "image": image,
        "sds_url": sds_url,
        "source": source
    }
