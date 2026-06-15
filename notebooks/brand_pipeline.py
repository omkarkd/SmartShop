"""
Brand Extraction Pipeline
=========================
Processes ALL products from Aldi and Sainsbury's collections in MongoDB,
extracts brands from product names using the brand knowledge base,
and stores the transformed data in a new `branded_products` collection.

Usage:  python -m notebooks.brand_pipeline
"""
import sys, os, csv, re, json
from datetime import datetime, timezone
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymongo
from pymongo.errors import DuplicateKeyError

# ── Config ──────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("DB_NAME", "smartshop")
OUTPUT_COLLECTION = "branded_products"

KNOWLEDGE_BASE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "notebook", "llm_master_brand.csv"
)
UNKNOWN_BRANDS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "notebook", "sains_unknown_brands.csv"
)

# ── 1. Load brand knowledge base ────────────────────────────────────
def load_knowledge_base(path):
    """Load llm_master_brand.csv into {product_name_lower: brand} dict."""
    known = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["names"].strip()
            brand = row["Brand"].strip()
            if brand and brand != "Unknown":
                known[name.lower()] = brand
    return known

def load_unknown_brands(path):
    """Load sains_unknown_brands.csv into a simple frequency dict."""
    freq = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = row["clean_name"]
            count = int(row["count"])
            # Parse list-like string: "['heinz']" -> "heinz"
            m = re.search(r"'([^']+)'", raw)
            if m:
                word = m.group(1).lower()
                freq[word] = freq.get(word, 0) + count
    return freq

# ── 2. Build brand registry ─────────────────────────────────────────
def build_registry(knowledge_base):
    """
    Build a registry keyed by brand_lower.
    Each entry knows:
      brand      – canonical brand name
      examples   – product names from the KB
      variants   – first words of product names that may indicate this brand
    """
    registry = {}
    for product_name, brand in knowledge_base.items():
        bl = brand.lower()
        if bl not in registry:
            registry[bl] = {
                "brand": brand,
                "examples": [],
                "variants": set(),
            }
        registry[bl]["examples"].append(product_name)
        first_word = product_name.split()[0].lower().strip("'\"")
        registry[bl]["variants"].add(first_word)
    return registry

# ── 3. Normalisation helper ─────────────────────────────────────────
def norm(text):
    return re.sub(r"\s+", " ", text.lower()).strip()

# ── 4. Extraction strategies ────────────────────────────────────────
def score_prefix(text, registry, min_len=3):
    """Brand appears as prefix of product name."""
    n = norm(text)
    best_b, best_s = None, 0.0
    for bl, info in registry.items():
        if len(bl) < min_len:
            continue
        if n.startswith(bl):
            s = min(1.0, 0.7 + len(bl) / 50)
            if s > best_s:
                best_s, best_b = s, info["brand"]
        for v in info["variants"]:
            if len(v) < min_len:
                continue
            if n.startswith(v):
                s = 0.5 + len(v) / 30
                if s > best_s:
                    best_s, best_b = s, info["brand"]
    return best_b, best_s

def score_anywhere(text, registry, min_len=3):
    """Brand appears anywhere in product name. Skips very short terms."""
    n = norm(text)
    best_b, best_s = None, 0.0
    for bl, info in registry.items():
        if len(bl) < min_len:
            continue
        if bl in n:
            bonus = 0.1 if n.startswith(bl) else 0
            s = 0.6 + bonus + len(bl) / 60
            if s > best_s:
                best_s, best_b = s, info["brand"]
    return best_b, best_s

def score_fuzzy(text, registry, threshold=0.75, min_len=3):
    """Fuzzy n-gram match against known brands. Skips short terms."""
    n = norm(text)
    words = n.split()
    if len(words) < 1:
        return None, 0.0
    best_b, best_s = None, 0.0
    for ng in range(1, min(5, len(words) + 1)):
        for i in range(len(words) - ng + 1):
            ngram = " ".join(words[i:i+ng])
            for bl, info in registry.items():
                if len(bl) < min_len:
                    continue
                sim = SequenceMatcher(None, ngram, bl).ratio()
                if sim >= threshold and sim > best_s:
                    best_s, best_b = sim, info["brand"]
    return best_b, best_s

# ── 5. Main extraction ──────────────────────────────────────────────
def extract_brand(text, registry):
    brand, score, method = None, 0.0, "none"

    b1, s1 = score_prefix(text, registry)
    if b1 and s1 >= 0.7:
        return b1, round(s1, 2), "prefix"

    b2, s2 = score_anywhere(text, registry)
    if b2 and s2 >= 0.6:
        return b2, round(s2, 2), "anywhere"

    b3, s3 = score_fuzzy(text, registry)
    if b3 and s3 >= 0.75:
        return b3, round(s3, 2), "fuzzy"

    return None, 0.0, "none"

# ── 6. Own-brand detection ──────────────────────────────────────────
KNOWN_OWN_BRANDS = {
    "aldi": {
        "cowbelle", "emporium", "specially selected", "everyday essentials",
        "actileaf", "village bakery", "holly lane", "merevale",
        "nature's pick", "the fishmonger", "dessert menu",
        "ashfields", "bramwells", "daisy", "delicato", "gianni's",
        "grandessa", "hartford house", "harvest morn", "hog roast co",
        "indian express", "kingsland", "kirkwood", "labour and wait",
        "little angels", "little monkey", "mamma mia", "mani life",
        "marcus", "mennai", "milka", "milkshake", "mister choc",
        "mornflake", "moser roth", "mountleigh", "my sweet peanut",
        "natural collection", "nature's kitchen", "neals yard", "noble",
        "oakhurst", "ollie & co", "ostrich", "pip & nut",
        "plant menu", "purbeck", "red fox", "restore & revive",
        "roberts", "rosemary co", "ruby", "savor", "scotts",
        "seriously", "sierra", "simply", "so delicious", "so organic",
        "southern", "stamford street co.", "stefano",
        "sundance kitchen", "tamara", "the collection",
        "the foodie market", "the luxury collection", "town", "village",
        "warrendale", "warrington", "westlers", "whog", "wolds",
        "york", "yorkshire",
    },
    "sainsburys": {
        "sainsbury's", "taste the difference", "habitat",
        "so organic", "freefrom", "love life",
    },
}

def detect_own_brand(brand, retailer):
    if not brand:
        return False
    bl = brand.lower().strip()
    for ob in KNOWN_OWN_BRANDS.get(retailer, set()):
        if bl == ob.lower():
            return True
    return False

# ── 7. Pipeline runner ─────────────────────────────────────────────
def run_pipeline():
    print("=" * 60)
    print("Brand Extraction Pipeline")
    print("=" * 60)

    # Connect
    client = pymongo.MongoClient(MONGO_URI)
    db = client[DB_NAME]
    out = db[OUTPUT_COLLECTION]

    # Load knowledge
    print(f"\nLoading knowledge base from {KNOWLEDGE_BASE}...")
    kb = load_knowledge_base(KNOWLEDGE_BASE)
    print(f"  {len(kb)} product→brand mappings loaded")

    registry = build_registry(kb)
    print(f"  {len(registry)} unique brands in registry")

    # ── Stop words (never add these as brands) ──
    STOP_WORDS = {
        "the", "a", "an", "and", "or", "in", "on", "at", "to", "for",
        "of", "with", "by", "is", "it", "as", "be", "are", "was",
        "la", "le", "les", "de", "du", "des", "il", "el", "un", "une",
        "del", "della", "das", "der", "die", "den", "ein", "eine",
        "dr", "bio", "ltd", "co", "uk", "london",
    }
    MIN_BRAND_LEN = 3  # ignore single/double character "brands"

    # Load unknown brands for supplementary matching
    if os.path.exists(UNKNOWN_BRANDS):
        print(f"Loading unknown brands from {UNKNOWN_BRANDS}...")
        unknown_freq = load_unknown_brands(UNKNOWN_BRANDS)
        print(f"  {len(unknown_freq)} candidate words loaded")

        # Add high-frequency unknown brands to registry
        added = 0
        for word, freq in sorted(unknown_freq.items(), key=lambda x: -x[1]):
            if word not in registry and freq >= 300:
                if word.lower() in STOP_WORDS:
                    continue
                if len(word) < MIN_BRAND_LEN:
                    continue
                registry[word] = {
                    "brand": word.title(),
                    "examples": [],
                    "variants": {word},
                }
                added += 1
        print(f"  Added {added} high-frequency candidate words to registry")
        print(f"  Registry now has {len(registry)} brands (after unknown augmentation)")

    # Drop & re-create output collection
    out.drop()
    print(f"\nOutput collection '{OUTPUT_COLLECTION}' created")

    # Process each source
    sources = [
        ("aldi_products", "aldi"),
        ("sainsburys_products", "sainsburys"),
    ]
    total_processed = 0
    total_matched = 0
    total_unmatched = 0

    for coll_name, retailer in sources:
        source = db[coll_name]
        total = source.count_documents({})
        print(f"\n{'─' * 50}")
        print(f"Processing {coll_name} ({total} docs)…")
        print(f"{'─' * 50}")

        batch = []
        for doc in source.find():
            product_name = doc.get("product_name", "")
            original_brand = doc.get("brand")
            is_own_brand_default = doc.get("is_own_brand", False)

            # Extract brand from product name
            extracted_brand, confidence, method = extract_brand(
                product_name, registry
            )

            # Determine final brand
            # If original_brand is already set and non-null, prefer it
            if original_brand and str(original_brand).strip():
                final_brand = str(original_brand).strip()
                extraction_source = "original"
            elif extracted_brand:
                final_brand = extracted_brand
                extraction_source = method
            else:
                final_brand = None
                extraction_source = "none"

            # Detect own-brand
            is_own = detect_own_brand(final_brand, retailer) if final_brand else False

            # Build output doc
            out_doc = {
                "source_collection": coll_name,
                "source_id": doc["_id"],
                "product_name": product_name,
                "category": doc.get("category"),
                "price": doc.get("price"),
                "retailer": retailer,
                "original_brand": original_brand,
                "extracted_brand": extracted_brand,
                "extraction_confidence": confidence,
                "extraction_method": extraction_source,
                "final_brand": final_brand,
                "is_own_brand": is_own,
                "is_own_brand_original": is_own_brand_default,
                "processed_at": datetime.now(timezone.utc),
            }

            batch.append(out_doc)
            total_processed += 1

            if final_brand:
                total_matched += 1
            else:
                total_unmatched += 1

            # Insert in batches of 500
            if len(batch) >= 500:
                out.insert_many(batch)
                batch = []

        if batch:
            out.insert_many(batch)

        print(f"  Done: {total} processed from {coll_name}")

    # Index the output
    out.create_index("product_name")
    out.create_index("final_brand")
    out.create_index("retailer")
    out.create_index("category")
    out.create_index("extraction_method")

    print(f"\n{'=' * 60}")
    print(f"Pipeline complete!")
    print(f"  Total products processed: {total_processed}")
    print(f"  With brand:              {total_matched}")
    print(f"  No brand found:          {total_unmatched}")
    print(f"  Collection:              {DB_NAME}.{OUTPUT_COLLECTION}")
    print(f"{'=' * 60}")

    # Quick summary
    print(f"\nBrand extraction methods:")
    pipeline = [
        {"$group": {"_id": "$extraction_method", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    for r in out.aggregate(pipeline):
        print(f"  {r['_id']:>10s}: {r['count']:>5d}")

    print(f"\nTop 20 extracted brands:")
    pipeline = [
        {"$match": {"extraction_method": {"$ne": "original"}}},
        {"$group": {"_id": "$final_brand", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 20},
    ]
    for r in out.aggregate(pipeline):
        print(f"  {str(r['_id']):>30s}: {r['count']:>5d}")

    client.close()

if __name__ == "__main__":
    run_pipeline()
