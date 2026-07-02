import streamlit as st
import pandas as pd
from shared.db import get_db


@st.cache_data(ttl=120)
def get_db_overview():
    db = get_db()
    info = {}
    try:
        stats = db.command("dbStats")
        info["db_stats"] = {
            "total_size": _bytes_to_human(stats.get("totalSize", 0)),
            "objects": stats.get("objects", 0),
            "data_size": _bytes_to_human(stats.get("dataSize", 0)),
            "collections": stats.get("collections", 0),
        }
    except Exception:
        info["db_stats"] = {"total_size": "-", "objects": 0, "data_size": "-", "collections": 0}

    cols = []
    consumer = {
        "users": "User accounts",
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
        cols.append({"name": name, "type": "consumer", "description": desc, "documents": count})
    for name, desc in internal.items():
        try:
            count = db[name].count_documents({}) if name in db.list_collection_names() else 0
        except Exception:
            count = 0
        cols.append({"name": name, "type": "internal", "description": desc, "documents": count})

    info["collections"] = cols
    return info


def _bytes_to_human(b):
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def show():
    data = get_db_overview()
    db_stats = data.get("db_stats", {})
    cols = data.get("collections", [])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Size", db_stats.get("total_size", "-"))
    col2.metric("Documents", f"{db_stats.get('objects', 0):,}")
    col3.metric("Data Size", db_stats.get("data_size", "-"))
    col4.metric("Collections", db_stats.get("collections", 0))

    st.subheader("Collections")

    consumer = [c for c in cols if c.get("type") == "consumer"]
    internal = [c for c in cols if c.get("type") == "internal"]

    tab1, tab2 = st.tabs([f"Consumer ({len(consumer)})", f"Internal ({len(internal)})"])

    with tab1:
        if consumer:
            st.dataframe(pd.DataFrame(consumer), use_container_width=True, hide_index=True)
        else:
            st.info("No consumer collections")

    with tab2:
        if internal:
            st.dataframe(pd.DataFrame(internal), use_container_width=True, hide_index=True)
        else:
            st.info("No internal collections")

    st.subheader("Collection Metrics")
    if cols:
        import plotly.express as px
        cdf = pd.DataFrame(cols)
        fig = px.bar(cdf, x="name", y="documents", color="type",
                     title="Documents per Collection",
                     labels={"name": "Collection", "documents": "Documents", "type": "Type"})
        st.plotly_chart(fig, use_container_width=True)
