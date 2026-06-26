import os
import time
import threading
import subprocess
import sys
import shutil
from datetime import datetime, timezone
from typing import Optional
from pymongo import MongoClient, DESCENDING
import streamlit as st

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "smartshop")

_client = None

_SCRAPER_THREADS = {}


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


# ── Dashboard ──

def get_dashboard_overview():
    db = get_db()
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    results = {}

    try:
        results["scraper_summary"] = list(db["performance_metrics"].aggregate([
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
        ]))
    except Exception:
        results["scraper_summary"] = []

    try:
        results["today_category_stats"] = list(db["performance_metrics"].aggregate([
            {"$match": {"type": "category_scrape", "timestamp": {"$gte": today_start}}},
            {"$group": {
                "_id": "$retailer",
                "categories_success": {"$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}},
                "categories_failed": {"$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}},
                "total_products_found": {"$sum": "$product_count"},
            }}
        ]))
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
            count = db[name].count_documents({}) if name in db.list_collection_names() else 0
        except Exception:
            count = 0
        info.append({"name": name, "type": "internal", "description": desc, "documents": count})
    return info


def _bytes_to_human(b):
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


# ── Scraping Runs ──

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


# ── Scrape Queue / Runner ──

def queue_scrape_run(retailer: str, scheduled: bool = False) -> Optional[str]:
    db = get_db()
    entry = {
        "type": "scrape_request",
        "retailer": retailer,
        "status": "queued",
        "scheduled": scheduled,
        "created_at": datetime.now(timezone.utc),
        "started_at": None,
        "completed_at": None,
        "log": [],
    }
    result = db["scrape_requests"].insert_one(entry)
    return str(result.inserted_id)


def append_scrape_log(request_id: str, line: str):
    from bson.objectid import ObjectId
    try:
        db = get_db()
        db["scrape_requests"].update_one(
            {"_id": ObjectId(request_id)},
            {"$push": {"log": line}}
        )
    except Exception:
        pass


def get_scrape_logs(request_id: str) -> list:
    from bson.objectid import ObjectId
    try:
        db = get_db()
        doc = db["scrape_requests"].find_one({"_id": ObjectId(request_id)})
        return doc.get("log", []) if doc else []
    except Exception:
        return []


def get_queued_runs(limit: int = 50):
    db = get_db()
    try:
        return list(db["scrape_requests"].find().sort("created_at", DESCENDING).limit(limit))
    except Exception:
        return []


def update_queue_status(request_id, status, **kwargs):
    from bson.objectid import ObjectId
    db = get_db()
    update = {"$set": {"status": status, **kwargs}}
    db["scrape_requests"].update_one({"_id": ObjectId(request_id)}, update)


def get_active_request() -> Optional[dict]:
    db = get_db()
    try:
        doc = db["scrape_requests"].find_one(
            {"status": {"$in": ["queued", "running"]}},
            sort=[("created_at", DESCENDING)]
        )
        return doc
    except Exception:
        return None


def run_scraper_background(request_id: str, retailer: str):
    db = get_db()
    PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

    def _log(line):
        with open("/tmp/scraper_progress.log", "a") as f:
            f.write(f"[{request_id[:8]}] {line}\n")
        append_scrape_log(request_id, line)

    try:
        _log(f"Starting scraper for {retailer}...")
        update_queue_status(request_id, "running", started_at=datetime.now(timezone.utc))

        env = os.environ.copy()
        env["RETAILER"] = retailer
        env["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        env["DB_NAME"] = os.getenv("DB_NAME", "smartshop")
        env["CHROME_HEADLESS"] = "true"
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONPATH"] = PROJECT_DIR

        proc = subprocess.Popen(
            [sys.executable, "-m", "scrapper.docker_entry"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            cwd=PROJECT_DIR,
        )

        for raw_line in iter(proc.stdout.readline, ""):
            line = raw_line.rstrip("\n\r")
            if line:
                print(line, flush=True)
                _log(line)

        proc.wait()
        exit_code = proc.returncode

        if exit_code == 0:
            _log(f"Scraper completed successfully (exit code {exit_code})")
            update_queue_status(request_id, "completed",
                                completed_at=datetime.now(timezone.utc))
        else:
            _log(f"Scraper finished with exit code {exit_code}")
            update_queue_status(request_id, "failed",
                                completed_at=datetime.now(timezone.utc),
                                exit_code=exit_code)

    except Exception as e:
        err = f"Scraper error: {e}"
        _log(err)
        update_queue_status(request_id, "failed",
                            completed_at=datetime.now(timezone.utc),
                            error=str(e))


def start_scraper_thread(request_id: str, retailer: str):
    thread = threading.Thread(
        target=run_scraper_background,
        args=(request_id, retailer),
        daemon=True,
        name=f"scraper-{request_id[:8]}",
    )
    _SCRAPER_THREADS[request_id] = thread
    thread.start()
    return thread


def can_run_scraper() -> tuple:
    chrome_binary = (
        shutil.which("google-chrome") or
        shutil.which("google-chrome-stable") or
        shutil.which("chromium-browser") or
        shutil.which("chromium") or
        shutil.which("/usr/bin/chromium") or
        (os.path.isfile("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
         and "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome") or
        None
    )
    if chrome_binary:
        return (True, chrome_binary)
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import undetected_chromedriver; print('ok')"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return (True, "undetected_chromedriver (Chrome auto-download)")
    except Exception:
        pass
    return (False, None)
