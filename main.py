# main.py
from flask import Flask, request, jsonify
from scraper import scrape_product
import os

app = Flask(__name__)

@app.route('/scrape', methods=['GET'])
def scrape():
    product_name = request.args.get('productName')
    if not product_name:
        return jsonify({"error": "Missing productName parameter"}), 400

    try:
        result = scrape_product(product_name)
        if result:
            return jsonify(result), 200
        else:
            return jsonify({"error": "Product not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
