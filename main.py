from flask import Flask, request, jsonify
import os
from scraper import scrape_product

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
    result = scrape_product(product_name)
    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
