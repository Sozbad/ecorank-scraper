import os
import requests
from flask import Flask, request, jsonify
from firebase_admin import credentials, firestore, initialize_app
from google_sds_fallback import scrape_google_fallback
from utils.image_and_description import fetch_image_and_description  # custom util for description/image fallback

# Firebase setup
import firebase_admin
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    initialize_app(cred)
db = firestore.client()
products_ref = db.collection("products")

app = Flask(__name__)

@app.route("/")
def health():
    return "EcoRank scraper is live."

@app.route("/scrape", methods=["GET"])
def scrape():
    product_name = request.args.get("productName")
    if not product_name:
        return jsonify({"error": "Missing productName"}), 400

    doc_id = product_name.strip().lower()
    existing = products_ref.document(doc_id).get()
    if existing.exists:
        return jsonify(existing.to_dict())

    print(f"🧠 Scraping fallback for: {product_name}")

    # 1. SDS fallback
    sds_data = scrape_google_fallback(product_name)
    if not sds_data:
        return jsonify({"error": "No SDS PDF found in Google results"}), 404

    # 2. Image + description fallback
    desc_data = fetch_image_and_description(product_name)

    final_doc = {
        "name": product_name,
        "hazards": sds_data.get("hazards", ["not found"]),
        "disposal": sds_data.get("disposal", "not found"),
        "sds_url": sds_data.get("sds_url", ""),
        "source": sds_data.get("source", "google_sds_fallback"),
        "score": "not found",
        "image": desc_data.get("image", "not found"),
        "description": desc_data.get("description", "not found"),
        "data_quality": sds_data.get("data_quality", "partial")
    }

    products_ref.document(doc_id).set(final_doc)
    return jsonify(final_doc)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
