from pymongo import MongoClient, ASCENDING
from backend.config import MONGO_URI, DB_NAME


client = MongoClient(MONGO_URI)
db = client[DB_NAME]

users_collection = db["users"]
carts_collection = db["carts"]
cart_items_collection = db["cart_items"]
aldi_products = db["aldi_products"]
sainsburys_products = db["sainsburys_products"]


def ensure_indexes():
    users_collection.create_index("email", unique=True)
    carts_collection.create_index("user_id")
    cart_items_collection.create_index("cart_id")
    cart_items_collection.create_index([("cart_id", ASCENDING), ("match_key", ASCENDING)])
    aldi_products.create_index([("product_name", ASCENDING)])
    sainsburys_products.create_index([("product_name", ASCENDING)])
    aldi_products.create_index([("category", ASCENDING)])
    sainsburys_products.create_index([("category", ASCENDING)])
