import os
from flask import Flask, request, jsonify
from firebase_admin import credentials, firestore, initialize_app
import firebase_admin

from scraper import get_product_data

app = Flask(__name__)

# ✅ Initialize Firebase correctly
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    initialize_app(cred)
db = firestore.client()
products_ref = db.collection("products")


@app.route("/")
def health():
    return "EcoRank scraper is live."


@app.route("/scrape", methods=["GET"])
def scrape():
    product_name = request.args.get("productName")
    if not product_name:
        return jsonify({"error": "Missing productName"}), 400

    # Check Firestore cache
    existing = products_ref.document(product_name.lower()).get()
    if existing.exists:
        return jsonify(existing.to_dict())

    # Run scrape
    data = get_product_data(product_name)
    if not data or not data.get("hazards") or data["hazards"] == ["not found"]:
        return jsonify({"error": "No SDS PDF found in Google results"}), 404

    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
