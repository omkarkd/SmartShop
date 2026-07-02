import re
from difflib import SequenceMatcher
from backend.database import aldi_products, sainsburys_products

STOP_WORDS = {
    "the", "and", "for", "with", "from", "this", "that",
    "free", "fresh", "british", "value", "sainsburys",
    "taste", "difference", "filtered", "organic",
}

BRAND_ALIASES = {
    "sainsbury's": "own brand",
    "aldi": "own brand",
    "cowbelle": "own brand",
    "merevale": "own brand",
    "holly lane": "own brand",
    "nature's pick": "own brand",
    "village bakery": "own brand",
    "dessert menu": "own brand",
    "the fishmonger": "own brand",
    "specially selected": "own brand",
}


def normalize_name(name):
    if not name:
        return ""
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def extract_size(name):
    if not name:
        return ""
    match = re.search(r"(\d+)\s*(g|kg|ml|l|cl|ea|pack|pk)", name.lower())
    if match:
        return match.group(0)
    return ""


def get_important_words(name):
    words = normalize_name(name).split()
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def word_overlap_ratio(n1, n2):
    w1 = set(get_important_words(n1))
    w2 = set(get_important_words(n2))
    if not w1 or not w2:
        return 0
    intersection = w1 & w2
    union = w1 | w2
    return len(intersection) / len(union)


def score_match(p1, p2):
    n1 = normalize_name(p1.get("product_name", ""))
    n2 = normalize_name(p2.get("product_name", ""))
    if not n1 or not n2:
        return 0

    overlap = word_overlap_ratio(n1, n2)
    seq_sim = SequenceMatcher(None, n1, n2).ratio()
    name_sim = max(overlap, seq_sim * 0.7 + overlap * 0.3)

    b1 = (p1.get("brand") or "").lower().strip()
    b2 = (p2.get("brand") or "").lower().strip()
    b1 = BRAND_ALIASES.get(b1, b1)
    b2 = BRAND_ALIASES.get(b2, b2)

    c1 = (p1.get("category", "") or "").lower().split(" > ")[-1].strip()[:15]
    c2 = (p2.get("category", "") or "").lower().split(" > ")[-1].strip()[:15]

    brand_bonus = 0.15 if b1 and b2 and b1 == b2 else 0
    cat_bonus = 0.1 if c1 and c2 and c1 == c2 else 0

    s1 = extract_size(n1)
    s2 = extract_size(n2)
    size_bonus = 0.1 if s1 and s2 and s1 == s2 else 0

    return name_sim + brand_bonus + cat_bonus + size_bonus


def find_matches(product, retailer, min_score=0.3, limit=3):
    target_col = sainsburys_products if retailer == "aldi" else aldi_products
    target_retailer = "sainsburys" if retailer == "aldi" else "aldi"

    name = product.get("product_name", "")

    name_words = get_important_words(name)
    candidates = []
    if name_words:
        or_filters = [{"product_name": {"$regex": re.escape(w), "$options": "i"}} for w in name_words[:5]]
        candidates = list(target_col.find({"$or": or_filters}, {"_id": 0}).limit(30))
    else:
        short_words = normalize_name(name).split()
        if short_words:
            or_filters = [{"product_name": {"$regex": re.escape(w), "$options": "i"}} for w in short_words[:3]]
            candidates = list(target_col.find({"$or": or_filters}, {"_id": 0}).limit(20))

    scored = [(score_match(product, c), c) for c in candidates]
    scored.sort(key=lambda x: -x[0])
    scored = [s for s in scored if s[0] >= min_score]

    results = []
    for score, doc in scored[:limit]:
        doc["retailer"] = target_retailer
        doc["match_score"] = round(score, 2)
        raw = doc.get("price")
        if raw is not None:
            try:
                doc["price"] = float(raw)
            except (ValueError, TypeError):
                m = re.search(r"(\d+\.?\d*)", str(raw))
                doc["price"] = float(m.group(1)) if m else None
        else:
            doc["price"] = None
        results.append(doc)

    return results
