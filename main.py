from flask import Flask, request, jsonify
import os
import traceback

try:
    from scraper import try_primary_sources, saveProductToFirestore
    from google_sds_fallback import search_google_sds_fallback
except Exception as e:
    print("Startup failure:", e)
    traceback.print_exc()
    raise e

app = Flask(__name__)

@app.route("/", methods=["GET"])
def root():
    return "EcoRank scraper is live."

@app.route("/scrape", methods=["POST"])
def scrape():
    try:
        data = request.get_json()
        if not data or "product_name" not in data:
            return jsonify({"error": "Missing product_name"}), 400

        product_name = data["product_name"]
        print(f"[INFO] Received scrape request for: {product_name}")

        # Try primary sources
        print("[INFO] Trying primary sources...")
        sds_data = try_primary_sources(product_name)
        print("[INFO] Primary result:", sds_data)

        if sds_data:
            saveProductToFirestore(sds_data)
            print("[INFO] Saved primary result to Firestore.")
            return jsonify(sds_data)

        # Fallback to Google SDS
        print("[INFO] Trying Google SDS fallback...")
        fallback = search_google_sds_fallback(product_name)
        print("[INFO] Fallback result:", fallback)

        if fallback and fallback.get("hazards"):
            saveProductToFirestore(fallback)
            print("[INFO] Saved fallback result to Firestore.")
            return jsonify(fallback)

        # Still nothing — store incomplete product
        print("[WARN] No data found. Storing incomplete record.")
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

    except Exception as e:
        print("Error during scrape:", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"[BOOT] Starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port)
