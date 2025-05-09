import os
from flask import Flask, request, jsonify
from utils.google_sds_fallback import search_google_for_sds_pdf, extract_sds_data_from_pdf
from utils.image_and_description import fetch_image_and_description
from firebase_utils import saveProductToFirestore

app = Flask(__name__)

@app.route("/")
def health_check():
    return "EcoRank scraper is running."

@app.route("/scrape", methods=["GET", "POST"])
def scrape():
    product_name = request.args.get("product_name") or (
        request.get_json(silent=True) or {}
    ).get("product_name")

    if not product_name:
        return jsonify({"error": "Missing product_name"}), 400

    # Start with default structure
    product_data = {
        "name": product_name,
        "hazards": ["not found"],
        "disposal": "not found",
        "description": "not found",
        "image": "not found",
        "sds_url": "",
        "source": "unknown",
        "score": "not found",
        "missingFields": []
    }

    # 1. Search Google for SDS PDF and extract
    try:
        pdf_url = search_google_for_sds_pdf(product_name)
        if pdf_url:
            sds_data = extract_sds_data_from_pdf(pdf_url)
            if sds_data:
                product_data.update(sds_data)
    except Exception as e:
        print("⚠️ SDS scraping failed:", e)

    # 2. Search for product image/description
    try:
        details = fetch_image_and_description(product_name)
        product_data.update(details)
    except Exception as e:
        print("⚠️ Visual scrape failed:", e)

    # 3. Flag missing fields
    for field in ["hazards", "disposal", "image", "description"]:
        if product_data[field] == "not found" or product_data[field] == ["not found"]:
            product_data["missingFields"].append(field)

    # 4. Save to Firestore
    try:
        saveProductToFirestore(product_data)
    except Exception as e:
        print("❌ Firestore error:", e)
        return jsonify({"error": "Failed to save"}), 500

    return jsonify(product_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
