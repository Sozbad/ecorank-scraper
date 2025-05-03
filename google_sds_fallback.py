from pathlib import Path

# Define the updated google_sds_fallback.py with logic to handle empty hazard codes
updated_google_sds_fallback = """
import requests
import fitz  # PyMuPDF
import re
from io import BytesIO

def extract_from_pdf(pdf_url):
    try:
        response = requests.get(pdf_url, timeout=15)
        response.raise_for_status()

        with BytesIO(response.content) as data:
            doc = fitz.open(stream=data, filetype="pdf")
            full_text = ""
            for page in doc:
                full_text += page.get_text()

            hazard_codes = re.findall(r'\\bH[2-4]\\d{2}\\b', full_text)
            hazard_codes = list(set(hazard_codes))

            # Try to extract disposal section (Section 13)
            disposal = ""
            section_13_match = re.search(r'(Section\\s*13[:\\-]? Disposal Considerations.*?)Section\\s*14', full_text, re.DOTALL | re.IGNORECASE)
            if section_13_match:
                disposal = section_13_match.group(1).strip()

            return {
                "hazard_codes": hazard_codes,
                "disposal": disposal or "not found",
                "data_quality": "high" if hazard_codes else "low",
                "score": 0 if not hazard_codes else None,
                "recommended": False if not hazard_codes else None
            }

    except Exception as e:
        print(f"PDF parse error: {e}")
        return {
            "hazard_codes": [],
            "disposal": "not found",
            "data_quality": "error",
            "score": 0,
            "recommended": False
        }
"""

# Save to file
parser_path = Path("/mnt/data/google_sds_fallback.py")
parser_path.write_text(updated_google_sds_fallback)

parser_path.name
