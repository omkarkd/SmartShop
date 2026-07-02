import re
from backend.database import db
from backend.services.brand_service import extract_brand as extract_brand_from_name

_branded = db["branded_products"]

SIZE_PATTERN = re.compile(
    r"("
    r"\d+\.?\d*\s*(?:l|ml|cl|g|kg|oz|lb)s?"
    r"|"
    r"\d+\s*(?:pint|pints)"
    r"|"
    r"\(\s*\d+\s*pint\s*\)"
    r")",
    re.IGNORECASE
)


def extract_size(text):
    if not text:
        return None
    m = SIZE_PATTERN.search(text)
    if m:
        raw = m.group(1)
        return raw.split("(")[0].strip()
    return None


def remove_size(text):
    return SIZE_PATTERN.sub("", text).strip()


def clean_product_name(name, brand):
    cleaned = remove_size(name)
    if brand and cleaned.lower().startswith(brand.lower()):
        cleaned = cleaned[len(brand):].strip().lstrip("'s-, \t").strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def normalize_product(doc, retailer):
    raw_name = doc.get("product_name", "") or ""
    source_id = doc.get("_id")

    entry = _branded.find_one({"source_id": source_id, "source_collection": f"{retailer}_products"})

    if entry and entry.get("final_brand"):
        brand = entry["final_brand"]
    else:
        brand, _, _ = extract_brand_from_name(raw_name)

    size = extract_size(raw_name)
    if not size:
        size = doc.get("size")
    cleaned_name = clean_product_name(raw_name, brand)

    nectar_price = doc.get("nectar_price")
    nectar_price = float(nectar_price) if nectar_price is not None else None

    return {
        "_id": str(source_id) if source_id else None,
        "product_name": cleaned_name or raw_name,
        "brand": brand or "",
        "size": size or "",
        "price": float(doc["price"]) if doc.get("price") else None,
        "retailer": retailer,
        "category": doc.get("category", ""),
        "original_name": raw_name,
        "image_url": doc.get("image_url") or "",
        "url": doc.get("url") or "",
        "price_per_unit": doc.get("price_per_unit") or "",
        "is_own_brand": entry.get("is_own_brand", False) if entry else doc.get("is_own_brand", False),
        "extraction_method": entry.get("extraction_method", "none") if entry else "none",
        "nectar_price": nectar_price,
        "nectar_price_label": doc.get("nectar_price_label"),
    }
