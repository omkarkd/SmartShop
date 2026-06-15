"""
Product name normalizer for grocery data.
Transforms raw product names into structured (brand, product, size, attributes).
Applies to Milk and Cheese categories only.
"""
import re

# ── Custom title case (handles apostrophes: "sainsbury's" -> "Sainsbury's") ──
def proper_title(s):
    """Like .title() but doesn't capitalise after apostrophes."""
    return re.sub(r"\b(\w)([\w']*)", lambda m: m.group(1).upper() + m.group(2).lower(), s)


# ── Size patterns ──────────────────────────────────────────────
SIZE_PATTERN = re.compile(
    r"("
    r"\d+\.?\d*\s*(?:l|ml|cl|g|kg|oz|lb)s?"          # 2L, 568ml, 400g, 1.5kg
    r"|"
    r"\d+\s*(?:pint|pints)"                            # 2 pint, 1 pint
    r"|"
    r"\(\s*\d+\s*pint\s*\)"                            # (2 pint), (4 pint)
    r")",
    re.IGNORECASE
)

# ── Brand prefixes found in product names ──────────────────────
BRAND_PREFIXES = {
    "sainsbury's", "cravendale", "arla", "yeo valley", "graham's",
    "st helen's farm", "cathedral city", "pilgrims choice",
    "philadelphia", "dairylea", "stamford street co.",
    "babybel", "primula", "boursin", "brie de meaux",
    "ragstone", "sartori", "comte", "roquefort",
}

# ── Known Aldi own-brands (lowercase for matching) ─────────────
ALDI_BRANDS = {
    "cowbelle", "emporium", "specially selected", "everyday essentials",
    "actileaf", "village bakery", "holly lane", "merevale",
    "nature's pick", "dessert menu", "the fishmonger",
}

# ── Product type keywords (ordered by specificity) ─────────────
MILK_TYPES = [
    "semi skimmed milk", "semi-skimmed milk",
    "skimmed milk",
    "whole milk",
    "lactose free milk",
    "chocolate flavoured protein milkshake",
    "strawberry flavoured protein milkshake",
    "chocolate extra thick milkshake",
    "strawberry extra thick milkshake",
    "banana extra thick milkshake",
    "chocolate fudge extra thick milkshake",
    "chocolate fudge milk",
    "milkshake",
    "milk",
]

CHEESE_TYPES = [
    "extra mature cheddar cheese", "mature cheddar cheese", "mild cheddar cheese",
    "cheddar cheese", "grated mozzarella", "mozzarella cheese",
    "mozzarella", "grated mature cheddar",
    "cream cheese", "soft cheese", "cottage cheese",
    "goats cheese", "goat's cheese",
    "feta cheese", "greek feta", "feta",
    "halloumi", "parmigiano reggiano", "parmesan",
    "mascarpone", "ricotta", "brie", "camembert",
    "stilton", "blue cheese", "red leicester",
    "double gloucester", "cheshire cheese", "lancashire cheese",
    "wensleydale", "edam", "gouda", "emmental",
    "cheese singles", "cheese slices", "cheddar slices",
    "greek style salad cheese", "cheese 'a' peel",
    "mozzarella di bufala", "burrata",
    "cheese",
]

FAT_PATTERN = re.compile(r"[<]?\d+\.?\d*\s*%\s*fat", re.IGNORECASE)


def extract_size(text):
    """Extract size from product name string."""
    if not text:
        return None
    m = SIZE_PATTERN.search(text)
    if m:
        raw = m.group(1)
        return raw.split("(")[0].strip()
    return None


def extract_brand_from_name(text, known_brand_field=None):
    """Extract brand prefix from product name, falling back to known brand field."""
    lower = text.lower()
    for brand in sorted(BRAND_PREFIXES | ALDI_BRANDS, key=len, reverse=True):
        if lower.startswith(brand):
            return proper_title(brand)
        pattern = re.compile(r"^\s*" + re.escape(brand) + r"[\s,'s]*", re.IGNORECASE)
        if pattern.match(lower):
            return proper_title(brand)
    if known_brand_field:
        return proper_title(known_brand_field)
    return None


def extract_product_type(text, category_hint="milk"):
    """Extract the core product type from the name."""
    lower = text.lower()
    types = MILK_TYPES if "milk" in category_hint.lower() else CHEESE_TYPES
    for ptype in sorted(types, key=len, reverse=True):
        if ptype in lower:
            return proper_title(ptype)
    return None


def remove_size(text):
    """Remove size information from the name."""
    return SIZE_PATTERN.sub("", text).strip()


def remove_fat(text):
    """Remove fat percentage."""
    return FAT_PATTERN.sub("", text).strip()


def normalize_milk_cheese_product(doc, retailer):
    """
    Normalize a single milk/cheese product document.

    Returns dict with:
      - product_name: clean core name (e.g. "Whole Milk")
      - brand: extracted brand (e.g. "Cowbelle", "Sainsbury's")
      - size: extracted size (e.g. "2.27L", "1L")
      - price: original price
      - attributes: list of modifiers (e.g. ["Organic", "Filtered"])
      - retailer: original retailer
      - original_name: original product name
      - category: original category
    """
    raw_name = doc.get("product_name", "")
    known_brand = doc.get("brand")
    category = doc.get("category", "")
    price = doc.get("price")
    raw_size = doc.get("size")

    # Step 1: Clean the name — remove fat percentage first
    cleaned = remove_fat(raw_name)

    # Step 2: Extract size
    size = extract_size(cleaned)
    if not size and raw_size:
        size = raw_size
    cleaned = remove_size(cleaned)

    # Step 3: Extract brand
    if retailer == "aldi":
        brand = proper_title(known_brand or "")
    else:
        brand = extract_brand_from_name(cleaned, known_brand)
        if brand and cleaned.lower().startswith(brand.lower()):
            cleaned = cleaned[len(brand):].strip().lstrip("'s").strip()

    if not brand:
        brand = extract_brand_from_name(raw_name, known_brand)

    if not brand:
        brand = proper_title(known_brand or "")

    # Step 4: Extract product type
    product_type = extract_product_type(cleaned, category)

    # Step 5: Extract modifiers from the remaining text
    remaining = cleaned.lower()
    if product_type:
        remaining = remaining.replace(product_type.lower(), "")
    if brand and brand.lower() in remaining:
        remaining = remaining.replace(brand.lower(), "")
    remaining = re.sub(r"\s+", " ", remaining).strip()
    remaining = remaining.strip("-, \t\n")
    remaining = re.sub(r"\s*\(.*?\)", "", remaining)

    attributes = []
    attr_keywords = [
        "organic", "filtered", "fresh", "british", "uht",
        "lactose free", "free range", "so organic",
        "taste the difference", "jersey", "skimed",
        "semi", "whole",
    ]
    for kw in attr_keywords:
        if kw in remaining:
            attributes.append(proper_title(kw))

    # Step 6: Fallback product type if none found
    if not product_type:
        if "milk" in category.lower():
            if "whole" in cleaned.lower():
                product_type = "Whole Milk"
            elif "semi" in cleaned.lower():
                product_type = "Semi Skimmed Milk"
            elif "skim" in cleaned.lower():
                product_type = "Skimmed Milk"
            else:
                product_type = "Milk"
        elif "cheese" in category.lower() or "cheese" in raw_name.lower():
            product_type = "Cheese"
        else:
            product_type = cleaned or raw_name

    # Remove duplicate words in product type
    pt_lower = product_type.lower()
    if pt_lower.count("milk") > 1 or pt_lower.count("cheese") > 1:
        parts = product_type.split()
        seen = set()
        unique = []
        for p in parts:
            low = p.lower()
            if low in seen:
                continue
            seen.add(low)
            unique.append(p)
        product_type = " ".join(unique)

    return {
        "product_name": product_type,
        "brand": brand,
        "size": size,
        "price": float(price) if price else None,
        "attributes": attributes,
        "retailer": retailer,
        "original_name": raw_name,
        "category": category,
    }


def get_milk_cheese_products(db, retailer="aldi"):
    """Get all milk and cheese products from a retailer."""
    collection = db[f"{retailer}_products"]
    products = list(collection.find({
        "$or": [
            {"category": {"$regex": "Milk", "$options": "i"}},
            {"category": {"$regex": "Cheese", "$options": "i"}},
        ]
    }, {"_id": 0}))

    if retailer == "sainsburys":
        products = [
            p for p in products
            if "baby" not in p.get("category", "").lower()
        ]

    return [normalize_milk_cheese_product(p, retailer) for p in products]


def find_by_product_name(normalized_products, query):
    """Search normalized products by name (case-insensitive, partial match)."""
    query = query.lower()
    results = []
    for p in normalized_products:
        name = p["product_name"].lower()
        if query in name:
            results.append(p)
    return results
