import os
import time
import threading
import subprocess
import sys
from datetime import datetime, timezone
from typing import Optional
from pymongo import MongoClient, DESCENDING
import bcrypt
import streamlit as st

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "smartshop")

_client = None


def get_db():
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client[DB_NAME]


def verify_admin(username: str, password: str) -> bool:
    return username == "admin" and password == "admin"


def login_required():
    if "admin_logged_in" not in st.session_state or not st.session_state.admin_logged_in:
        st.warning("Please login from the home page first")
        st.stop()


def get_dashboard_overview():
    db = get_db()
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    results = {}

    run_pipeline = [
        {"$match": {"type": "scraper_run"}},
        {"$sort": {"timestamp": -1}},
        {"$group": {
            "_id": "$retailer",
            "last_run": {"$first": "$timestamp"},
            "last_status": {"$first": "$status"},
            "last_products": {"$first": "$products_total"},
            "last_duration": {"$first": "$duration_seconds"},
            "total_runs": {"$sum": 1},
            "avg_products": {"$avg": "$products_total"},
        }}
    ]
    try:
        results["scraper_summary"] = list(db["performance_metrics"].aggregate(run_pipeline))
    except Exception as e:
        results["scraper_summary"] = []
        results["_error"] = str(e)

    try:
        today_cats = list(db["performance_metrics"].aggregate([
            {"$match": {"type": "category_scrape", "timestamp": {"$gte": today_start}}},
            {"$group": {
                "_id": "$retailer",
                "categories_success": {"$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}},
                "categories_failed": {"$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}},
                "total_products_found": {"$sum": "$product_count"},
            }}
        ]))
        results["today_category_stats"] = today_cats
    except Exception:
        results["today_category_stats"] = []

    try:
        results["today_runs"] = db["performance_metrics"].count_documents({
            "type": "scraper_run", "timestamp": {"$gte": today_start}
        })
    except Exception:
        results["today_runs"] = 0

    try:
        stats = db.command("dbStats")
        results["db_stats"] = {
            "collections": stats.get("collections", 0),
            "objects": stats.get("objects", 0),
            "data_size": _bytes_to_human(stats.get("dataSize", 0)),
            "storage_size": _bytes_to_human(stats.get("storageSize", 0)),
            "total_size": _bytes_to_human(stats.get("totalSize", 0)),
        }
    except Exception:
        results["db_stats"] = {}

    results["collections"] = _get_collection_info(db)
    return results


def _get_collection_info(db):
    info = []
    consumer = {
        "users": "User accounts",
        "carts": "Shopping carts",
        "cart_items": "Cart line items",
        "aldi_products": "Aldi catalog",
        "sainsburys_products": "Sainsbury's catalog",
    }
    internal = {
        "aldi_scrape_log": "Aldi audit log",
        "sainsburys_scrape_log": "Sainsbury's audit log",
        "performance_metrics": "Performance metrics",
        "scrape_requests": "Scrape job queue",
    }
    for name, desc in consumer.items():
        try:
            count = db[name].count_documents({})
        except Exception:
            count = 0
        info.append({"name": name, "type": "consumer", "description": desc, "documents": count})
    for name, desc in internal.items():
        try:
            count = db[name].count_documents({})
        except Exception:
            if name == "scrape_requests":
                count = 0
            else:
                count = 0
        info.append({"name": name, "type": "internal", "description": desc, "documents": count})
    return info


def _bytes_to_human(b):
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def get_scraping_runs(date_from=None, date_to=None, retailer=None, status=None, page=1, per_page=20):
    db = get_db()
    match = {"type": "scraper_run"}
    if date_from:
        match["timestamp"] = {"$gte": date_from}
    if date_to:
        match["timestamp"] = {**match.get("timestamp", {}), "$lte": date_to.replace(hour=23, minute=59, second=59)}
    if retailer:
        match["retailer"] = retailer
    if status:
        match["status"] = status

    try:
        total = db["performance_metrics"].count_documents(match)
        cursor = db["performance_metrics"].find(match).sort("timestamp", DESCENDING)
        cursor = cursor.skip((page - 1) * per_page).limit(per_page)
        runs = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if hasattr(doc.get("timestamp"), "isoformat"):
                doc["timestamp"] = doc["timestamp"].isoformat()
            runs.append(doc)
        return runs, total
    except Exception as e:
        return [], 0


def get_run_detail(run_id: str) -> dict:
    from bson.objectid import ObjectId
    db = get_db()
    try:
        run = db["performance_metrics"].find_one({"_id": ObjectId(run_id)})
        if not run:
            return {"error": "Run not found"}
        run["_id"] = str(run["_id"])
        if hasattr(run.get("timestamp"), "isoformat"):
            run["timestamp"] = run["timestamp"].isoformat()

        retailer = run.get("retailer", "")
        categories = list(db["performance_metrics"].find({
            "type": "category_scrape", "retailer": retailer,
        }).sort("timestamp", DESCENDING).limit(500))
        for c in categories:
            c["_id"] = str(c["_id"])
            if hasattr(c.get("timestamp"), "isoformat"):
                c["timestamp"] = c["timestamp"].isoformat()
        run["categories"] = categories
        return run
    except Exception as e:
        return {"error": str(e)}


QUEUED_RUNS = {}
RUNNER_THREAD = None


def queue_scrape_run(retailer: str, scheduled: bool = False):
    db = get_db()
    entry = {
        "type": "scrape_request",
        "retailer": retailer,
        "status": "queued",
        "scheduled": scheduled,
        "created_at": datetime.now(timezone.utc),
        "started_at": None,
        "completed_at": None,
    }
    db["scrape_requests"].insert_one(entry)
    return entry


def get_queued_runs():
    db = get_db()
    try:
        return list(db["scrape_requests"].find().sort("created_at", DESCENDING).limit(50))
    except Exception:
        return []


def update_queue_status(request_id, status, **kwargs):
    from bson.objectid import ObjectId
    db = get_db()
    update = {"$set": {"status": status, **kwargs}}
    db["scrape_requests"].update_one({"_id": ObjectId(request_id)}, update)


def can_run_scraper():
    try:
        result = subprocess.run(
            ["python", "-c", "import undetected_chromedriver; print('ok')"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False
