import re, pymongo
from backend.database import aldi_products, sainsburys_products, db
from backend.config import MONGO_URI, DB_NAME
from backend.services.normalizer_service import normalize_product

_client = pymongo.MongoClient(MONGO_URI)
_db = _client[DB_NAME]
_branded = _db["branded_products"]

PRODUCT_FIELDS = {
    "_id": 1,
    "url": 1,
    "product_name": 1,
    "category": 1,
    "brand": 1,
    "price": 1,
    "was_price": 1,
    "price_with_promotion": 1,
    "price_per_unit": 1,
    "image_url": 1,
    "is_own_brand": 1,
    "size": 1,
    "promotion_badge": 1,
    "nectar_price": 1,
    "nectar_price_label": 1,
}


def _get_brand_filter(brand):
    """Get list of product source_ids for a given brand from branded_products."""
    ids = _branded.find({"final_brand": brand}, {"source_id": 1})
    return [d["source_id"] for d in ids]


def _get_common_brands():
    """Return brands that have products in BOTH retailers."""
    pipeline = [
        {"$group": {"_id": "$final_brand", "retailers": {"$addToSet": "$retailer"}}},
        {"$match": {"retailers": {"$size": 2}}},
        {"$group": {"_id": None, "brands": {"$push": "$_id"}}},
    ]
    result = list(_branded.aggregate(pipeline))
    if result:
        return result[0]["brands"]
    return []


def search_products(query: str, retailer: str = None, category: str = None, brand: str = None, page: int = 1, per_page: int = 20):
    regex = re.compile(re.escape(query), re.IGNORECASE)
    and_filters = [{"product_name": regex}]
    if category:
        and_filters.append({"category": {"$regex": re.escape(category), "$options": "i"}})
    if brand:
        source_ids = _get_brand_filter(brand)
        and_filters.append({"_id": {"$in": source_ids}})

    common_mode = retailer == "common"
    if common_mode:
        common_brands = _get_common_brands()
        source_ids = _branded.find({"final_brand": {"$in": common_brands}}, {"source_id": 1})
        common_ids = [d["source_id"] for d in source_ids]
        and_filters.append({"_id": {"$in": common_ids}})
        retailer = None

    results = []
    collections = []
    if retailer is None or retailer == "aldi":
        collections.append(("aldi", aldi_products))
    if retailer is None or retailer == "sainsburys":
        collections.append(("sainsburys", sainsburys_products))

    for r, col in collections:
        cursor = col.find({"$and": and_filters}, PRODUCT_FIELDS).skip((page - 1) * per_page).limit(per_page)
        for doc in cursor:
            normalized = normalize_product(doc, r)
            results.append(normalized)

    results.sort(key=lambda x: x.get("price") or 0)
    return results


def get_categories(retailer: str = None):
    collections = []
    if retailer is None or retailer == "aldi":
        collections.append(("aldi", aldi_products))
    if retailer is None or retailer == "sainsburys":
        collections.append(("sainsburys", sainsburys_products))

    cats = set()
    for r, col in collections:
        for doc in col.find({}, {"category": 1}):
            if doc.get("category"):
                cats.add((doc["category"], r))
    return sorted(cats)


def get_products_by_category(category: str, retailer: str = None, brand: str = None, page: int = 1, per_page: int = 20):
    results = []
    and_filters = [{"category": category}]
    if brand:
        source_ids = _get_brand_filter(brand)
        and_filters.append({"_id": {"$in": source_ids}})

    common_mode = retailer == "common"
    if common_mode:
        common_brands = _get_common_brands()
        source_ids = _branded.find({"final_brand": {"$in": common_brands}}, {"source_id": 1})
        common_ids = [d["source_id"] for d in source_ids]
        and_filters.append({"_id": {"$in": common_ids}})
        retailer = None

    collections = []
    if retailer is None or retailer == "aldi":
        collections.append(("aldi", aldi_products))
    if retailer is None or retailer == "sainsburys":
        collections.append(("sainsburys", sainsburys_products))

    for r, col in collections:
        cursor = col.find({"$and": and_filters}, PRODUCT_FIELDS).skip((page - 1) * per_page).limit(per_page)
        for doc in cursor:
            normalized = normalize_product(doc, r)
            results.append(normalized)
    return results


def get_product_by_url(url: str):
    for col, retailer in [(aldi_products, "aldi"), (sainsburys_products, "sainsburys")]:
        doc = col.find_one({"url": url}, PRODUCT_FIELDS)
        if doc:
            normalized = normalize_product(doc, retailer)
            return normalized
    return None
