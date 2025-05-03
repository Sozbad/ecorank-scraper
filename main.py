from scraper import try_primary_sources, saveProductToFirestore
from google_sds_fallback import search_google_sds_fallback

def enrich_product(product_name):
    # First try main sources
    sds_data = try_primary_sources(product_name)

    if sds_data:
        return saveProductToFirestore(sds_data)

    # Fallback to Google SDS search
    fallback_data = search_google_sds_fallback(product_name)

    if fallback_data and fallback_data.get("hazards"):
        return saveProductToFirestore(fallback_data)

    # Still nothing – mark as incomplete
    return saveProductToFirestore({
        "name": product_name,
        "hazards": "not found",
        "disposal": "not found",
        "sds_url": None,
        "source": "Google fallback failed",
        "score": 0,
        "incomplete": True
    })
