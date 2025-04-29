from flask import Flask, request, jsonify
from scraper import scrape_product

app = Flask(__name__)

@app.route("/scrape")
def scrape_route():
    product_name = request.args.get("productName", "").strip()
    print(f"🔍 Incoming scrape for: {product_name}")
    if not product_name:
        return jsonify({"error": "Missing productName"}), 400
    result = scrape_product(product_name)
    print(f"✅ Result: {result}")
    return jsonify(result), 200 if "error" not in result else 404

@app.route("/")
def root():
    return "EcoRank scraper online.", 200
