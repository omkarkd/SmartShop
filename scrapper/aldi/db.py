import os
from pymongo import MongoClient, ASCENDING, DESCENDING, errors
from datetime import datetime, timezone


class AldiDB:
    def __init__(self, uri=None, db_name=None):
        self.uri = uri or os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = db_name or os.environ.get("DB_NAME", "smartshop")
        self._connect()

    def _connect(self):
        self.client = MongoClient(
            self.uri,
            maxIdleTimeMS=60000,
            connectTimeoutMS=15000,
            socketTimeoutMS=60000,
            serverSelectionTimeoutMS=60000,
            tlsInsecure=True,
        )
        self.db = self.client[self.db_name]
        self.products = self.db["aldi_products"]
        self.scrape_log = self.db["aldi_scrape_log"]
        try:
            self._ensure_indexes()
        except Exception:
            pass

    def _auto_reconnect(self, f, *args, **kwargs):
        max_attempts = 4
        for attempt in range(max_attempts):
            try:
                return f(*args, **kwargs)
            except (errors.ServerSelectionTimeoutError, errors.ConnectionFailure, errors.NetworkTimeout,
                    errors.AutoReconnect, errors.NotPrimaryError, errors.OperationFailure) as e:
                if attempt < max_attempts - 1:
                    print(f"    DB connection lost (attempt {attempt+1}/{max_attempts}: {e})")
                    import time
                    time.sleep(2 ** attempt)
                    self._connect()
                else:
                    print(f"    DB connection lost — all {max_attempts} attempts failed")
                    raise

    def _ensure_indexes(self):
        self.products.create_index([("url", ASCENDING)], unique=True, sparse=True)
        self.products.create_index([("category", ASCENDING)])
        self.products.create_index([("scraped_at", DESCENDING)])
        self.scrape_log.create_index([("url", ASCENDING)])
        self.scrape_log.create_index([("scraped_at", DESCENDING)])

    def product_exists(self, url):
        if not url:
            return False
        return self._auto_reconnect(
            lambda: self.products.find_one({"url": url}, {"_id": 1}) is not None
        )

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
            def _do_insert():
                for p in products:
                    self.products.update_one(
                        {"url": p["url"]},
                        {"$set": p},
                        upsert=True
                    )
                return True
            return self._auto_reconnect(_do_insert)
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
            def _do_log():
                self.scrape_log.insert_one(entry)
            self._auto_reconnect(_do_log)
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
        return self._auto_reconnect(
            lambda: list(self.products.aggregate(pipeline))
        )

    def get_total_product_count(self):
        return self._auto_reconnect(lambda: self.products.count_documents({}))

    def close(self):
        self.client.close()
