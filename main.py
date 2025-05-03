from flask import Flask, request, jsonify
import os
from scraper import scrape_product
from google_sds_fallback import search_google_sds_fallback

app = Flask(__name__)

@app.route("/", methods=["GET"])
def root():
    return "EcoRank scraper is live."

@app.route("/scrape", methods=["POST"])
def scrape():
    data = request.get_json()
    if not data or "product_name" not in data:
        return jsonify({"error": "Missing product_name"}), 400

    product_name = data["product_name"]
    print(f"Received scrape request for: {product_name}")

    # Primary scrape
    print("Trying primary sources...")
    sds_data = try_primary_sources(product_name)
    if sds_data:
        print("Primary source SUCCESS")
        saveProductToFirestore(sds_data)
        return jsonify(sds_data)

    print("Primary source FAILED — trying Google SDS fallback")
    fallback = search_google_sds_fallback(product_name)
    if fallback and fallback.get("hazards"):
        print("Google fallback SUCCESS")
        saveProductToFirestore(fallback)
        return jsonify(fallback)

    print("Google fallback FAILED — returning minimal result")
    incomplete = {
        "name": product_name,
        "hazards": "not found",
        "disposal": "not found",
        "sds_url": None,
        "source": "Google fallback failed",
        "score": 0,
        "incomplete": True
    }
    saveProductToFirestore(incomplete)
    return jsonify(incomplete)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
