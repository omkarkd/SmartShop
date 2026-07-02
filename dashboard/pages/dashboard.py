import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from shared.db import get_db


def _bytes_to_human(b):
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


@st.cache_data(ttl=120)
def get_dashboard_data():
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
    collections = {
        "aldi_products": ("consumer", "Aldi product catalog"),
        "sainsburys_products": ("consumer", "Sainsbury's product catalog"),
        "users": ("consumer", "User accounts"),
        "aldi_scrape_log": ("internal", "Aldi scrape audit log"),
        "sainsburys_scrape_log": ("internal", "Sainsbury's scrape audit log"),
        "performance_metrics": ("internal", "Performance metrics"),
        "scrape_requests": ("internal", "Scrape job queue"),
    }
    for name, (ctype, desc) in collections.items():
        try:
            count = db[name].count_documents({}) if name in db.list_collection_names() else 0
        except Exception:
            count = 0
        info.append({"name": name, "type": ctype, "description": desc, "documents": count})
    return info


def show():
    data = get_dashboard_data()

    today_cats = data.get("today_category_stats", [])
    total_cat_ok = sum(r.get("categories_success", 0) for r in today_cats)
    total_cat_fail = sum(r.get("categories_failed", 0) for r in today_cats)
    total_products_today = sum(r.get("total_products_found", 0) for r in today_cats)
    today_runs = data.get("today_runs", 0)
    db_stats = data.get("db_stats", {})

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Today's Runs", today_runs)
    col2.metric("Today's Products", total_products_today)
    col3.metric("Categories Today", f"{total_cat_ok} / {total_cat_fail} fail")
    col4.metric("Database Size", db_stats.get("total_size", "-"))

    with st.expander("Today's Scraping Activity", expanded=True):
        if today_cats:
            rows = [{
                "Retailer": r.get("_id", "?"),
                "Categories OK": r.get("categories_success", 0),
                "Failed": r.get("categories_failed", 0),
                "Products Found": r.get("total_products_found", 0),
            } for r in today_cats]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No scraping activity today")

    with st.expander("Scraper Run History", expanded=True):
        summary = data.get("scraper_summary", [])
        if summary:
            rows = [{
                "Retailer": r["_id"],
                "Last Run": str(r.get("last_run", "-"))[:19],
                "Status": r.get("last_status", "-"),
                "Products": r.get("last_products", 0),
                "Avg Products": int(r.get("avg_products", 0)),
                "Total Runs": r.get("total_runs", 0),
            } for r in summary]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No scraper runs recorded yet")

    with st.expander("Collections Overview", expanded=True):
        cols = data.get("collections", [])
        if cols:
            st.dataframe(pd.DataFrame(cols), use_container_width=True, hide_index=True)
        else:
            st.info("No collection data")
