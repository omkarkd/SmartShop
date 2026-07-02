import os
import time
from datetime import datetime, timezone
from pymongo import MongoClient, errors


def _get_db():
    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "smartshop")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
    return client[db_name]


def record_scraper_run(retailer: str, categories_total: int, categories_success: int,
                       categories_failed: int, products_total: int, duration_seconds: float,
                       status: str = "completed", details: dict = None):
    metric = {
        "type": "scraper_run",
        "retailer": retailer,
        "categories_total": categories_total,
        "categories_success": categories_success,
        "categories_failed": categories_failed,
        "products_total": products_total,
        "duration_seconds": round(duration_seconds, 2),
        "status": status,
        "details": details or {},
        "timestamp": datetime.now(timezone.utc),
    }
    try:
        db = _get_db()
        db["performance_metrics"].insert_one(metric)
        print(f"  [metrics] scraper run recorded for {retailer}")
    except Exception as e:
        print(f"  [metrics] failed to record: {e}")


def record_category_scrape(retailer: str, category_name: str, url: str,
                           product_count: int, duration_seconds: float,
                           status: str = "success", error: str = None):
    metric = {
        "type": "category_scrape",
        "retailer": retailer,
        "category": category_name,
        "url": url,
        "product_count": product_count,
        "duration_seconds": round(duration_seconds, 2),
        "status": status,
        "error": error,
        "timestamp": datetime.now(timezone.utc),
    }
    try:
        db = _get_db()
        db["performance_metrics"].insert_one(metric)
    except Exception:
        pass


def get_latest_scraper_runs(limit: int = 10):
    try:
        db = _get_db()
        cursor = db["performance_metrics"].find(
            {"type": "scraper_run"}
        ).sort("timestamp", -1).limit(limit)
        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if isinstance(doc.get("timestamp"), datetime):
                doc["timestamp"] = doc["timestamp"].isoformat()
            results.append(doc)
        return results
    except Exception as e:
        return {"error": str(e)}


def get_scraper_summary():
    try:
        db = _get_db()
        pipeline = [
            {"$match": {"type": "scraper_run"}},
            {"$sort": {"timestamp": -1}},
            {"$group": {
                "_id": "$retailer",
                "last_run": {"$first": "$timestamp"},
                "last_products": {"$first": "$products_total"},
                "last_duration": {"$first": "$duration_seconds"},
                "last_status": {"$first": "$status"},
                "total_runs": {"$sum": 1},
                "avg_products": {"$avg": "$products_total"},
                "avg_duration": {"$avg": "$duration_seconds"},
            }}
        ]
        return list(db["performance_metrics"].aggregate(pipeline))
    except Exception as e:
        return {"error": str(e)}
