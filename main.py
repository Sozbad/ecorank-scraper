import os
from flask import Flask, request, jsonify
from google_sds_fallback import search_google_for_sds_pdf, extract_sds_data_from_pdf
from image_and_description import fetch_image_and_description
from firebase_utils import saveProductToFirestore

app = Flask(__name__)

@app.route("/")
def health_check():
    return "EcoRank scraper is running."

@app.route("/scrape", methods=["GET", "POST"])
def scrape():
    if request.method == "POST":
        data = request.get_json()
        product_name = data.get("product_name") if data else None
    else:
        product_name = request.args.get("product_name")

    if not product_name:
        return jsonify({"error": "Missing product_name"}), 400

    product_data = {
        "name": product_name,
        "hazards": ["not found"],
        "disposal": "not found",
        "description": "not found",
        "image": "not found",
        "sds_url": "",
        "source": "",
        "score": "not found",
        "missingFields": []
    }

    try:
        pdf_url = search_google_for_sds_pdf(product_name)
        if pdf_url:
            sds_data = extract_sds_data_from_pdf(pdf_url)
            if sds_data:
                product_data.update(sds_data)
    except Exception as e:
        print(f"⚠️ SDS scrape failed: {str(e)}")

    try:
        visual_data = fetch_image_and_description(product_name)
        product_data.update(visual_data)
    except Exception as e:
        print(f"⚠️ Visual scrape failed: {str(e)}")

    for key in ["hazards", "disposal", "image", "description"]:
        if product_data[key] == "not found" or product_data[key] == ["not found"]:
            product_data["missingFields"].append(key)

    try:
        saveProductToFirestore(product_data)
    except Exception as e:
        print(f"❌ Firestore save failed: {str(e)}")
        return jsonify({"error": "Failed to save to database"}), 500

    return jsonify(product_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
