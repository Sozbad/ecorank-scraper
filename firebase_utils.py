import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)

db = firestore.client()

def saveProductToFirestore(product):
    slug = product.get("name", "").lower().replace(" ", "-")
    data = {
        "name": product.get("name", "not found"),
        "hazards": product.get("hazards", ["not found"]),
        "disposal": product.get("disposal", "not found"),
        "description": product.get("description", "not found"),
        "image": product.get("image", "not found"),
        "sds_url": product.get("sds_url", ""),
        "source": product.get("source", "unknown"),
        "score": product.get("score", "not found"),
        "missingFields": product.get("missingFields", []),
        "lastUpdated": firestore.SERVER_TIMESTAMP
    }
    db.collection("products").document(slug).set(data, merge=True)
