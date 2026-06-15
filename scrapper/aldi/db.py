from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime, timezone


class AldiDB:
    def __init__(self, uri="mongodb://localhost:27017", db_name="smartshop"):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.products = self.db["aldi_products"]
        self.scrape_log = self.db["aldi_scrape_log"]
        self._ensure_indexes()

    def _ensure_indexes(self):
        self.products.create_index([("url", ASCENDING)], unique=True, sparse=True)
        self.products.create_index([("category", ASCENDING)])
        self.products.create_index([("scraped_at", DESCENDING)])
        self.scrape_log.create_index([("url", ASCENDING)])
        self.scrape_log.create_index([("scraped_at", DESCENDING)])

    def product_exists(self, url):
        if not url:
            return False
        return self.products.find_one({"url": url}, {"_id": 1}) is not None

    def insert_product(self, product):
        product["scraped_at"] = datetime.now(timezone.utc)
        try:
            result = self.products.update_one(
                {"url": product["url"]},
                {"$set": product},
                upsert=True
            )
            return result.upserted_id or True
        except Exception as e:
            print(f"    DB insert error: {e}")
            return None

    def insert_products(self, products):
        now = datetime.now(timezone.utc)
        for p in products:
            p["scraped_at"] = now
        if not products:
            return True
        try:
            for p in products:
                self.products.update_one(
                    {"url": p["url"]},
                    {"$set": p},
                    upsert=True
                )
            return True
        except Exception as e:
            print(f"    DB bulk insert error: {e}")
            return False

    def log_scrape(self, url, category_name, product_count, status="success", error=None, page=1):
        entry = {
            "url": url,
            "category": category_name,
            "product_count": product_count,
            "page": page,
            "status": status,
            "error": error,
            "scraped_at": datetime.now(timezone.utc)
        }
        try:
            self.scrape_log.insert_one(entry)
        except Exception as e:
            print(f"    DB log error: {e}")

    def get_category_stats(self, category_name=None):
        match = {"category": category_name} if category_name else {}
        pipeline = [
            {"$match": match},
            {"$group": {
                "_id": "$category",
                "product_count": {"$sum": 1},
                "last_scraped": {"$max": "$scraped_at"}
            }},
            {"$sort": {"_id": 1}}
        ]
        return list(self.products.aggregate(pipeline))

    def get_total_product_count(self):
        return self.products.count_documents({})

    def close(self):
        self.client.close()
