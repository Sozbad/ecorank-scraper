def map_phrase_to_hcode(text):
    mapping = {
        "Causes skin irritation": "H315",
        "May cause cancer": "H350",
        "Very toxic to aquatic life": "H400",
        "Fatal if inhaled": "H330",
        "Causes serious eye damage": "H318",
        "May cause respiratory irritation": "H335",
        "Toxic if swallowed": "H301",
        "Causes damage to organs": "H370",
        "Harmful if swallowed": "H302"
    }
    for phrase, hcode in mapping.items():
        if phrase.lower() in text.lower():
            return hcode
    if text.strip().startswith("H") and text.strip()[1:].isdigit():
        return text.strip()
    return None
