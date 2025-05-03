# firebase_utils.py
import firebase_admin
from firebase_admin import credentials, firestore
import os

# Prevent reinitialization during import
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
db = firestore.client()

def saveProductToFirestore(product):
    try:
        slug = product.get("slug", product.get("name", "unnamed-product")).replace(" ", "-").lower()
        doc_ref = db.collection("products").document(slug)
        doc_ref.set(product)
        print(f"✅ Saved to Firestore: {slug}")
    except Exception as e:
        print("❌ Firestore save error:", e)
