import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from shared.db import get_db


@st.cache_data(ttl=30)
def get_last_runs(limit=20):
    db = get_db()
    try:
        cursor = db["performance_metrics"].find(
            {"type": "scraper_run"}
        ).sort("timestamp", -1).limit(limit)
        runs = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if hasattr(doc.get("timestamp"), "isoformat"):
                doc["timestamp"] = doc["timestamp"].isoformat()
            runs.append(doc)
        return runs
    except Exception:
        return []


def show():
    st.subheader("Scraper Status")

    # ── Info banner ──
    st.info(
        "  **Scraper runs as a separate Render Cron Job.**\n\n"
        "The scraper is no longer triggered from this dashboard. "
        "It runs on a schedule (every 6 hours by default) as an "
        "independent Docker container and writes results to MongoDB.\n\n"
        "See the **Scraping Runs** tab for run history."
    )

    # ── Last runs ──
    st.markdown("### Recent Scraper Runs")
    runs = get_last_runs()
    if runs:
        rows = [{
            "Time": str(r.get("timestamp", ""))[:19],
            "Retailer": r.get("retailer", ""),
            "Status": r.get("status", ""),
            "Products": r.get("products_total", 0),
            "Duration": f'{r.get("duration_seconds", 0):.1f}s',
        } for r in runs]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No runs recorded yet. The first cron job will write results here.")

    # ── Schedule info ──
    st.markdown("### Schedule Configuration")
    st.markdown("""
The scraper is deployed as a **Render Cron Job** with the following schedule:

| Schedule | Retailer | Command |
|---|---|---|
| Every 6 hours | all | `RETAILER=all python -m scraper.main` |

To change the schedule, update the cron expression in Render's dashboard.
""")

    st.markdown("### Manual Trigger")
    st.code(
        "# SSH into the Render Cron Job shell or use Render dashboard:\n"
        "RETAILER=all python -m scraper.main",
        language="bash"
    )
