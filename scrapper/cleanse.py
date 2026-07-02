"""
Product data cleansing for SmartShop.
Extracts pack size and brand from raw product data.

Usage:
    python scrapper/cleanse.py --test                 # run tests (no DB)
    python scrapper/cleanse.py --uri <MONGO_URI>      # apply to MongoDB
    python scrapper/cleanse.py --uri <MONGO_URI> --dry-run  # preview only
"""

import re
import sys
from datetime import datetime, timezone
from pymongo import MongoClient, UpdateOne


# ============================================================
# Brand dictionary
# ============================================================

KNOWN_BRANDS = [
    "Sainsbury's", "Taste the Difference", "Love Life", "My Goodness!",
    "Habitat", "So Organic", "By Sainsbury's", "Stamford Street",
    # Baby & Toddler
    "Pampers", "Huggies", "Kiddilicious", "Ella's Kitchen", "Organix",
    "Aptamil", "Kendamil", "Cow & Gate", "Childs Farm", "Johnson's",
    "Johnson's Baby", "Rascals", "Bepanthen", "Sudocrem",
    "HiPP", "SMA", "Munchkin",
    # Drinks
    "Coca-Cola", "Diet Coke", "Fanta", "Sprite",
    "Dr Pepper", "Pepsi", "Pepsi Max", "7UP",
    "Tropicana", "Innocent", "Copella", "Robinsons", "Ribena",
    "Lucozade", "Lucozade Energy", "Lucozade Sport", "Powerade",
    "PG Tips", "Tetley", "Twinings", "Yorkshire Tea", "Pukka",
    "Nescafe", "Dolce Gusto", "Carte Noire", "Kenco", "Lavazza",
    "Whittard", "Schweppes", "Appletiser", "Fever-Tree",
    "Evian", "Volvic", "Highland Spring", "Oatly", "Alpro",
    "Starbucks", "Monster", "Gordon's", "Old Jamaica",
    # Food Cupboard
    "Heinz", "HP", "Lea & Perrins", "Colman's", "Sharwood's",
    "Hellmann's", "Dolmio", "Knorr", "Batchelors", "Ainsley Harriott",
    "Uncle Ben's", "Ben's Original", "Tilda", "Tilda Microwave",
    "Napolina", "Ciro", "Mutti", "Ciao",
    "John West", "Princes", "Branston", "Baxters", "Campbell's",
    "Bisto", "Oxo", "Kallo",
    "McVitie's", "Cadbury", "Galaxy", "Mars", "Snickers", "Twix",
    "Malteasers", "M&M's", "Skittles", "Starburst",
    "Walkers", "Pringles", "Doritos", "Monster Munch", "Wotsits",
    "Mr Kipling", "Jacob's", "Carr's", "Ryvita", "Nairn's",
    "Hartley's", "Rowntree's", "Thorntons",
    "Quaker", "Quaker Oat", "Jordans", "Kellogg's", "Weetabix", "Alpen",
    "Hovis", "Warburtons", "Kingsmill", "Roberts",
    "Pot Noodle", "Super Noodles", "Nutella",
    "Dunn's River", "Merchant Gourmet", "Doves Farm",
    "Ambrosia", "Bird's", "McDougalls",
    "Karyatis", "Tariq", "Gama", "KTC",
    # Frozen
    "Birds Eye", "Findus", "Young's", "McCain", "Aunt Bessie's",
    "Goodfella's", "Chicago Town", "Pizza Express",
    # Chilled
    "Muller", "Müller", "Yeo Valley", "Activia", "Actimel", "Danone",
    "Philadelphia", "Cathedral City", "Pilgrims Choice",
    "Lurpak", "Anchor", "Country Life", "Flora",
    "Arla", "St Helen's", "Cravendale", "Lindahls", "Elmlea",
    "Biotiful", "Plenish",
    # Meat & Fish
    "Quorn", "Linda McCartney", "Cauldron", "Richmond",
    "This Isn't", "Beyond Meat", "Beyond",
    # World Foods
    "Blue Dragon", "Patak's", "Geeta's", "Naked",
    "Crosta & Mollica", "Crosta", "Mollica",
    "La Famiglia Rana", "La Vie",
    "Bonne Maman", "Grace", "Nissin",
    # Free From
    "Schär", "Schar", "Doves Farm", "Maya Gold", "Violife", "BFree",
    # Household
    "Fairy", "Persil", "Ariel", "Bold", "Daz", "Surf", "Lenor",
    "Cillit Bang", "Domestos", "Mr Muscle", "Flash", "Finish",
    "Andrex", "Cushelle", "Velvet", "Kleenex",
    "Febreze", "Glade", "Air Wick", "Bacofoil", "Dettol",
    # Personal Care
    "Nivea", "Dove", "Lynx", "Sure", "Sanex",
    "Colgate", "Oral-B", "Sensodyne", "Aquafresh",
    "Pantene", "Head & Shoulders", "Herbal Essences", "Aussie",
    "Aveeno", "WaterWipes",
    # Pet
    "Friskies", "Whiskas", "Pedigree", "Bakers",
    "Felix", "Go-Cat", "Cesar", "Harringtons",
    # Brands from data scan
    "Allinson's", "BEAR", "BrewDog", "Comfort", "Dole",
    "Ginsters", "Graze", "itsu", "Jus-Rol", "Kiddylicious",
    "Magnum", "Mam", "Mission", "Nerds", "Nestle", "Nestlé",
    "NOMO", "Promise", "Rowse", "Rustlers", "Soreen",
    "Belvita", "Huel", "FUEL 10K",
    "Deliciously Ella", "Pip & Nut", "Angel Delight", "Bolands",
    "Higgidy", "Jason's", "Squeaky Bean",
    "Carte D'Or", "Pizza Express",
    "St. Pierre", "Pierre", "St. Ewe",
    "Old El Paso", "New Covent Garden", "New York Bakery Co.",
    "Plant Pioneers", "Plant Pioneer",
    "The Collective", "The Coconut Collab", "The Happy Egg Co.",
    "The Tofoo Co.", "The Ice Co.", "The Vegetarian Butcher",
    "The Spice Tailor", "The Groovy Food Company",
    "The Northern Dough Co.", "The Paleo Foods Co.",
    "The Vinegar Company", "The Cultured Collective",
    "The Floral Collection",
    "Little Dish", "Little Freddie", "Little Moons", "Little Ones",
    "Tommee Tippee", "Eat Natural", "Eat Real",
    "Dorset Cereals", "Village Bakery",
    "Tesco", "Asda", "Biona", "Clearspring", "Meridian",
]

BRAND_SET = {b.lower() for b in KNOWN_BRANDS}
BRANDS_BY_LENGTH = sorted(KNOWN_BRANDS, key=len, reverse=True)


def normalize_brand(brand: str | None) -> str | None:
    if not brand:
        return None
    brand = brand.strip().strip(",.:;!-'\"")
    if not brand:
        return None
    lower = brand.lower()
    for known in KNOWN_BRANDS:
        if lower == known.lower():
            return known
    return brand


def extract_brand(name: str, existing_brand: str | None = None) -> str | None:
    if existing_brand:
        cleaned = normalize_brand(existing_brand)
        if cleaned and cleaned.lower() in BRAND_SET:
            return cleaned

    if not name:
        return normalize_brand(existing_brand) if existing_brand else None

    name_clean = name.strip()

    for brand in BRANDS_BY_LENGTH:
        if name_clean.lower().startswith(brand.lower()):
            return brand

    words = name_clean.split()
    if len(words) >= 2:
        two_words = " ".join(words[:2]).rstrip(",.:;!-'\"")
        if two_words.lower() in BRAND_SET:
            return normalize_brand(two_words)

    first_word = words[0].rstrip(",.:;!-'\"")
    if first_word.lower() in BRAND_SET:
        return normalize_brand(first_word)

    return normalize_brand(existing_brand) if existing_brand else None


# ============================================================
# Pack size extraction
# ============================================================

SIZE_PATTERNS = [
    re.compile(r'(?P<count>\d+)\s*[×xX*]\s*(?P<size>[\d.]+)\s*(?P<unit>g|kg|ml|l|cl|oz|L)', re.IGNORECASE),
    re.compile(r'(?P<size>[\d.]+)\s*(?P<unit>g|kg|ml|l|cl|oz|L)\s*[-–]\s*(?P<size2>[\d.]+)\s*(?P<unit2>g|kg|ml|l|cl|oz|L)', re.IGNORECASE),
    re.compile(r'(?P<size>[\d.]+)\s*(?P<unit>g|kg|ml|l|cl|oz|L)\b', re.IGNORECASE),
    re.compile(r'[Pp]ack\s+[Oo]f\s+(?P<count>\d+)\s*(?P<unit>g|kg|ml|l|cl|oz|L)?'),
    re.compile(r'(?P<count>\d+)\s*[- ]?[Pp]ack'),
    re.compile(r'\b(?:each|single|1 each|per each)\b', re.IGNORECASE),
]

SKIP_WORDS = {"pack", "bag", "bottle", "can", "tub", "jar", "tin", "box",
              "carton", "pouch", "sachet", "roll", "bar", "tray", "pot"}

PPU_RE = re.compile(r'/(\d*)\s*(kg|g|kgs|l|ml|cl|oz|L)\b', re.IGNORECASE)


def _fmt(n: float | None) -> str | None:
    if n is None:
        return None
    return str(int(n)) if isinstance(n, float) and n == int(n) else str(n)


def _build_pack_result(
    pack_size: str | None,
    quantity: float | None = None,
    unit: str | None = None,
    multi_pack_count: int | None = None,
    multi_pack_size: float | None = None,
    multi_pack_unit: str | None = None,
    source: str | None = None,
) -> dict:
    return {
        "pack_size": pack_size,
        "quantity": quantity,
        "unit": unit,
        "multi_pack_count": multi_pack_count,
        "multi_pack_size": multi_pack_size,
        "multi_pack_unit": multi_pack_unit,
        "source": source,
    }


def _match_size(text: str, skip_pack_of: bool = False) -> dict | None:
    for pattern in SIZE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        gd = m.groupdict()

        if skip_pack_of and "count" in gd and not gd.get("size") and not gd.get("unit"):
            continue

        if gd.get("count") and gd.get("size"):
            count = int(gd["count"])
            size = float(gd["size"])
            unit = gd["unit"].lower() if gd.get("unit") else None
            return _build_pack_result(
                pack_size=f"{count} x {_fmt(size)}{unit}" if unit else f"{count} x {_fmt(size)}",
                quantity=size, unit=unit,
                multi_pack_count=count, multi_pack_size=size, multi_pack_unit=unit,
            )

        if gd.get("size2"):
            size = float(gd["size"])
            unit = gd["unit"].lower()
            size2 = float(gd["size2"])
            unit2 = gd["unit2"].lower()
            return _build_pack_result(
                pack_size=f"{_fmt(size)}{unit} - {_fmt(size2)}{unit2}",
                quantity=(size + size2) / 2, unit=unit,
            )

        if gd.get("size") and gd.get("unit"):
            size = float(gd["size"])
            unit = gd["unit"].lower()
            return _build_pack_result(
                pack_size=f"{_fmt(size)}{unit}",
                quantity=size, unit=unit,
            )

        if gd.get("count") and not gd.get("size"):
            count = int(gd["count"])
            unit = gd.get("unit", "").lower() if gd.get("unit") else ""
            label = f"Pack of {count}{unit}" if unit else f"Pack of {count}"
            return _build_pack_result(
                pack_size=label, unit=unit if unit else None,
                multi_pack_count=count,
            )

    return None


def _extract_unit_from_ppu(ppu: str | None) -> str | None:
    if not ppu:
        return None
    m = PPU_RE.search(ppu)
    if m:
        prefix = m.group(1).strip()
        unit = m.group(2).lower()
        return f"{prefix}{unit}" if prefix else unit
    return None


def extract_pack_size(
    name: str,
    size_field: str | None = None,
    price_per_unit: str | None = None,
) -> dict:
    if size_field:
        parsed = _match_size(size_field.strip())
        if parsed:
            parsed["source"] = "size_field"
            return parsed

    if name:
        cleaned = re.sub(r'\b(' + '|'.join(SKIP_WORDS) + r')\s+', ' ', name, flags=re.IGNORECASE)
        parsed = _match_size(cleaned, skip_pack_of=True)
        if parsed:
            parsed["source"] = "product_name"
            return parsed

    if price_per_unit:
        unit = _extract_unit_from_ppu(price_per_unit)
        if unit:
            return {
                "pack_size": f"per {unit}", "unit": unit,
                "source": "price_per_unit",
                "quantity": None, "multi_pack_count": None,
                "multi_pack_size": None, "multi_pack_unit": None,
            }

    return _build_pack_result(pack_size=None, source=None)


# ============================================================
# Product cleansing
# ============================================================

def cleanse_product(product: dict, retailer: str = "sainsburys") -> dict:
    name = product.get("product_name") or ""
    existing_brand = product.get("brand")
    size_field = product.get("size") if retailer == "aldi" else None
    ppu = product.get("price_per_unit")

    pack = extract_pack_size(name, size_field=size_field, price_per_unit=ppu)
    product["pack_size"] = pack["pack_size"]
    product["pack_quantity"] = pack["quantity"]
    product["pack_unit"] = pack["unit"]
    product["multi_pack_count"] = pack["multi_pack_count"]
    product["multi_pack_size"] = pack["multi_pack_size"]
    product["multi_pack_unit"] = pack["multi_pack_unit"]
    product["pack_size_source"] = pack.get("source")

    product["brand_clean"] = extract_brand(name, existing_brand=existing_brand)
    product["cleansed_at"] = datetime.now(timezone.utc)
    return product


def _build_update(doc: dict) -> UpdateOne:
    fields = {
        "pack_size", "pack_quantity", "pack_unit",
        "multi_pack_count", "multi_pack_size", "multi_pack_unit",
        "pack_size_source", "brand_clean", "cleansed_at",
    }
    return UpdateOne({"_id": doc["_id"]}, {"$set": {k: doc[k] for k in fields if k in doc}})


def process_collection(collection, retailer: str, dry_run: bool = False) -> int:
    query = {"cleansed_at": {"$exists": False}}
    total = collection.count_documents(query)
    print(f"  Found {total} products to cleanse")
    if total == 0:
        return 0

    processed = 0
    errors = 0
    batch = []
    cursor = collection.find(query, no_cursor_timeout=True)

    for doc in cursor:
        try:
            cleanse_product(doc, retailer=retailer)
            if dry_run:
                processed += 1
                if processed <= 5:
                    print(f"    [{processed}] {doc.get('product_name','?')[:60]}")
                    print(f"           pack_size={doc['pack_size']!r}, brand={doc['brand_clean']!r}")
                continue
            batch.append(_build_update(doc))
            processed += 1
            if len(batch) >= 100:
                collection.bulk_write(batch, ordered=False)
                print(f"    Progress: {processed}/{total}")
                batch = []
        except Exception as e:
            errors += 1
            print(f"    Error [{doc.get('_id')}]: {e}")

    if batch and not dry_run:
        collection.bulk_write(batch, ordered=False)
        print(f"    Final flush: {processed}/{total}")

    cursor.close()
    print(f"  Done: {processed} processed, {errors} errors")
    return processed


# ============================================================
# CLI
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cleanse SmartShop product data")
    parser.add_argument("--uri", help="MongoDB URI")
    parser.add_argument("--db", default="smartshop")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    if args.test:
        run_tests()
        return

    if not args.uri:
        print("Error: --uri is required (or use --test)")
        sys.exit(1)

    print(f"Connecting to {args.uri[:30]}...")
    client = MongoClient(args.uri)
    db = client[args.db]

    for col_name, retailer in [("sainsburys_products", "sainsburys"),
                                ("aldi_products", "aldi")]:
        if col_name not in db.list_collection_names():
            print(f"\n'{col_name}' not found, skipping")
            continue
        print(f"\nProcessing {col_name} ({retailer})")
        process_collection(db[col_name], retailer, dry_run=args.dry_run)

    client.close()
    print("\nDone.")


# ============================================================
# Tests
# ============================================================

def run_tests():
    passed = 0
    failed = 0
    total = 0

    def check(condition: bool, label: str):
        nonlocal passed, failed, total
        total += 1
        if condition:
            passed += 1
            print(f"  ✓ {label}")
        else:
            failed += 1
            print(f"  ✗ {label}")

    # --- Pack size ---
    print("=" * 60)
    print("Pack Size Extraction")
    print("=" * 60)

    cases = [
        ("Hovis Soft White Medium Bread 800g",     None, None, "800g",    800.0, "g"),
        ("McVitie's Digestives 500g",              None, None, "500g",    500.0, "g"),
        ("Ben & Jerry's Cookie Dough 465ml",       None, None, "465ml",   465.0, "ml"),
        ("Coca-Cola Zero Sugar 2L",                None, None, "2l",       2.0, "l"),
        ("Walkers Baked 6 x 150g",                 None, None, "6 x 150g", 150.0, "g"),
        ("Heinz Baked Beans 4x200g",               None, None, "4 x 200g", 200.0, "g"),
        ("Yeo Valley Yogurt 500g",                  None, None, "500g",   500.0, "g"),
        ("Product with 100g in middle",             None, None, "100g",   100.0, "g"),
        ("Fresh Bananas",                           None, None, None,      None, None),
        ("Pack of 6 Scones",                        None, None, None,      None, None),
        # Aldi size field
        ("Some Product", "500g",   None, "500g",   500.0, "g"),
        ("Some Product", "6x100g", None, "6 x 100g", 100.0, "g"),
        ("Some Product", "1L",     None, "1l",       1.0, "l"),
        # Price-per-unit fallback
        ("Milk",   None, "£1.50/L",      "per l",    None, "l"),
        ("Butter", None, "£0.75/100g",   "per 100g", None, "100g"),
    ]

    for name, sf, ppu, exp_size, exp_qty, exp_unit in cases:
        r = extract_pack_size(name, size_field=sf, price_per_unit=ppu)
        tag = name[:45]
        check(r["pack_size"] == exp_size, f"{tag:50s} → pack_size={r['pack_size']!r}")
        check(r["quantity"] == exp_qty,   f"{tag:50s} quantity={r['quantity']!r}")
        check(r["unit"] == exp_unit,      f"{tag:50s} unit={r['unit']!r}")

    # --- Brand ---
    print(f"\n{'=' * 60}")
    print("Brand Extraction")
    print("=" * 60)

    brand_cases = [
        ("Sainsbury's British Chicken 1kg",       None,       "Sainsbury's"),
        ("Taste the Difference Lasagne 400g",      None,       "Taste the Difference"),
        ("Heinz Tomato Ketchup 500g",              None,       "Heinz"),
        ("Hovis Soft White Bread 800g",            None,       "Hovis"),
        ("McVitie's Digestives 500g",              None,       "McVitie's"),
        ("Coca-Cola Zero Sugar 2L",                None,       "Coca-Cola"),
        ("Walkers Baked 6 x 150g",                 None,       "Walkers"),
        ("Nescafe Original 200g",                  None,       "Nescafe"),
        ("Fresh Bananas",                          None,       None),
        ("Bananas Loose",                          None,       None),
        ("Muller Light Yogurt",                    "Muller",   "Muller"),
        ("Unknown product",                        "SomeValue","SomeValue"),
        # Multi-word brand match
        ("Old El Paso Tortilla Wraps",             None,       "Old El Paso"),
        ("The Collective Yogurt",                  None,       "The Collective"),
        ("Little Dish Pasta Meal",                 None,       "Little Dish"),
        ("This Isn't Pork Sausages",               None,       "This Isn't"),
    ]

    for name, existing, expected in brand_cases:
        result = extract_brand(name, existing_brand=existing)
        check(result == expected, f"{name[:40]:40s} → {result!r}")

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print(f"{passed}/{total} passed")
    if failed:
        print(f"FAILURES: {failed}")
        sys.exit(1)
    else:
        print("All tests passed!")


if __name__ == "__main__":
    main()
