from flask import Flask, request, jsonify
from scraper import scrape_product

app = Flask(__name__)

@app.route("/")
def root():
    return "EcoRank scraper is running."

@app.route("/scrape", methods=["GET"])
def scrape_route():
    product_name = request.args.get("productName", "").strip()
    print(f"🔍 Received scrape request for: {product_name}")
    if not product_name:
        return jsonify({"error": "Missing productName"}), 400

    try:
        result = scrape_product(product_name)
        print(f"✅ Scrape result: {result}")
        return jsonify(result), 200 if "error" not in result else 404
    except Exception as e:
        print(f"❌ Internal server error: {e}")
        return jsonify({"error": "Internal error"}), 500

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
