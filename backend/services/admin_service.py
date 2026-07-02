from datetime import datetime, timezone
from typing import Optional
import bcrypt
from jose import jwt
from backend.config import SECRET_KEY, ALGORITHM
from backend.database import db

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = bcrypt.hashpw(b"admin", bcrypt.gensalt())


def verify_admin(username: str, password: str) -> bool:
    return username == ADMIN_USERNAME and bcrypt.checkpw(
        password.encode("utf-8"), ADMIN_PASSWORD_HASH
    )


def create_admin_token() -> str:
    expire = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59)
    payload = {"sub": "admin", "role": "admin", "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_admin_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("role") == "admin"
    except Exception:
        return False


def get_dashboard_overview() -> dict:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

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

    today_runs_pipeline = [
        {"$match": {"type": "scraper_run", "timestamp": {"$gte": today_start}}},
        {"$count": "count"},
    ]

    category_pipeline = [
        {"$match": {"type": "category_scrape"}},
        {"$sort": {"timestamp": -1}},
        {"$group": {
            "_id": None,
            "total_categories_scraped": {"$sum": 1},
            "avg_duration": {"$avg": "$duration_seconds"},
            "max_duration": {"$max": "$duration_seconds"},
        }}
    ]

    scrape_log_pipeline = [
        {"$match": {"timestamp": {"$gte": today_start}}},
        {"$group": {
            "_id": "$retailer",
            "categories_success": {
                "$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}
            },
            "categories_failed": {
                "$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}
            },
            "total_products_found": {"$sum": "$product_count"},
        }}
    ]

    results = {}
    try:
        results["scraper_summary"] = list(db["performance_metrics"].aggregate(run_pipeline))
        results["today_runs"] = list(db["performance_metrics"].aggregate(today_runs_pipeline))
        results["category_summary"] = list(db["performance_metrics"].aggregate(category_pipeline))
        results["today_category_stats"] = list(db["performance_metrics"].aggregate(scrape_log_pipeline))
    except Exception as e:
        results["_error"] = str(e)

    collection_info = _get_collection_info()
    db_stats = _get_db_stats()

    return {
        "server_time": now.isoformat(),
        "scraper_runs": results.get("scraper_summary", []),
        "today_runs": results["today_runs"][0]["count"] if results.get("today_runs") else 0,
        "today_category_stats": results.get("today_category_stats", []),
        "category_performance": results.get("category_summary", []),
        "collections": collection_info,
        "database": db_stats,
    }


def _get_collection_info() -> list:
    consumer_collections = {
        "users": "User accounts and auth",
        "carts": "Shopping carts",
        "cart_items": "Cart line items",
        "aldi_products": "Aldi product catalog (consumer-facing)",
        "sainsburys_products": "Sainsbury's product catalog (consumer-facing)",
    }
    internal_collections = {
        "aldi_scrape_log": "Aldi scrape audit log",
        "sainsburys_scrape_log": "Sainsbury's scrape audit log",
        "performance_metrics": "Performance and scraper metrics",
    }

    info = []
    for name, desc in consumer_collections.items():
        try:
            count = db[name].count_documents({})
        except Exception:
            count = -1
        info.append({
            "name": name,
            "type": "consumer",
            "description": desc,
            "document_count": count,
        })
    for name, desc in internal_collections.items():
        try:
            count = db[name].count_documents({})
        except Exception:
            count = -1
        info.append({
            "name": name,
            "type": "internal",
            "description": desc,
            "document_count": count,
        })
    return info


def _get_db_stats() -> dict:
    try:
        stats = db.command("dbStats")
        return {
            "collections": stats.get("collections", 0),
            "objects": stats.get("objects", 0),
            "data_size": _bytes_to_human(stats.get("dataSize", 0)),
            "storage_size": _bytes_to_human(stats.get("storageSize", 0)),
            "index_size": _bytes_to_human(stats.get("indexSize", 0)),
            "total_size": _bytes_to_human(stats.get("totalSize", 0)),
        }
    except Exception as e:
        return {"error": str(e)}


def _bytes_to_human(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def get_scraping_runs(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    retailer: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    match = {"type": "scraper_run"}
    if date_from:
        try:
            match["timestamp"] = {"$gte": datetime.fromisoformat(date_from)}
        except Exception:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to)
            match["timestamp"] = {**match.get("timestamp", {}), "$lte": dt.replace(hour=23, minute=59, second=59)}
        except Exception:
            pass
    if retailer:
        match["retailer"] = retailer
    if status:
        match["status"] = status

    try:
        total = db["performance_metrics"].count_documents(match)
        cursor = db["performance_metrics"].find(match).sort("timestamp", -1)
        cursor = cursor.skip((page - 1) * per_page).limit(per_page)
        runs = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if hasattr(doc.get("timestamp"), "isoformat"):
                doc["timestamp"] = doc["timestamp"].isoformat()
            runs.append(doc)
        return {"runs": runs, "total": total, "page": page, "per_page": per_page}
    except Exception as e:
        return {"error": str(e), "runs": [], "total": 0}


def get_scraping_run_detail(run_id: str) -> dict:
    from bson.objectid import ObjectId
    try:
        run = db["performance_metrics"].find_one({"_id": ObjectId(run_id)})
        if not run:
            return {"error": "Run not found"}
        run["_id"] = str(run["_id"])
        if hasattr(run.get("timestamp"), "isoformat"):
            run["timestamp"] = run["timestamp"].isoformat()

        categories = list(db["performance_metrics"].find({
            "type": "category_scrape",
            "retailer": run.get("retailer"),
        }).sort("timestamp", -1).limit(500))
        for c in categories:
            c["_id"] = str(c["_id"])
            if hasattr(c.get("timestamp"), "isoformat"):
                c["timestamp"] = c["timestamp"].isoformat()

        run["categories"] = categories
        return run
    except Exception as e:
        return {"error": str(e)}


def get_database_dashboard() -> dict:
    return {
        "db_stats": _get_db_stats(),
        "collections": _get_collection_info(),
        "consumer_collections": [c for c in _get_collection_info() if c["type"] == "consumer"],
        "internal_collections": [c for c in _get_collection_info() if c["type"] == "internal"],
    }


def get_service_health() -> dict:
    checks = {}

    try:
        db.command("ping")
        checks["mongodb"] = {"status": "healthy", "latency_ms": None}
        start = datetime.now(timezone.utc)
        db.command("ping")
        elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        checks["mongodb"]["latency_ms"] = round(elapsed, 2)
    except Exception as e:
        checks["mongodb"] = {"status": "unhealthy", "error": str(e)}

    try:
        import pymongo
        checks["pymongo_version"] = pymongo.version
    except Exception:
        pass

    try:
        import bcrypt
        checks["bcrypt_available"] = True
    except Exception:
        checks["bcrypt_available"] = False

    return checks
