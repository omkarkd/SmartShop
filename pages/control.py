import streamlit as st
import pandas as pd
import time
import threading
import subprocess
import sys
import os
from datetime import datetime, timezone
from bson.objectid import ObjectId
from utils import get_db, get_queued_runs, queue_scrape_run, update_queue_status, can_run_scraper


def _run_scraper(retailer: str, request_id: str):
    from utils import get_db
    db = get_db()
    try:
        update_queue_status(request_id, "running", started_at=datetime.now(timezone.utc))
        env = os.environ.copy()
        env["RETAILER"] = retailer
        env["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        env["DB_NAME"] = os.getenv("DB_NAME", "smartshop")
        env["CHROME_HEADLESS"] = "true"
        result = subprocess.run(
            [sys.executable, "-m", "scrapper.docker_entry"],
            capture_output=True, text=True, timeout=7200,
            env=env, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        update_queue_status(request_id, "completed",
                            completed_at=datetime.now(timezone.utc),
                            output=result.stdout[-2000:] if result.stdout else "",
                            errors=result.stderr[-2000:] if result.stderr else "")
    except subprocess.TimeoutExpired:
        update_queue_status(request_id, "timeout",
                            completed_at=datetime.now(timezone.utc))
    except Exception as e:
        update_queue_status(request_id, "failed",
                            completed_at=datetime.now(timezone.utc),
                            errors=str(e))


def show():
    st.subheader("Scraper Control")

    tab1, tab2, tab3 = st.tabs(["Start Scraping", "Schedule", "Run History"])

    with tab1:
        st.markdown("### Start a Scraping Run")

        retailer = st.radio("Select retailer", ["all", "aldi", "sainsburys"],
                            format_func=lambda x: {"all": "Both Retailers", "aldi": "Aldi",
                                                   "sainsburys": "Sainsbury's"}[x],
                            horizontal=True)

        st.info(
            "Starting a scrape will run the Selenium scraper which requires Chrome/Chromium. "
            "If Chrome is not available locally, the run will be queued for the Docker container."
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button(" Start Scraping Now", type="primary", use_container_width=True):
                entry = queue_scrape_run(retailer)
                request_id = str(entry.inserted_id) if hasattr(entry, "inserted_id") else None

                chrome_ok = can_run_scraper()
                if chrome_ok:
                    st.success(f"Starting scraper for {retailer}...")
                    thread = threading.Thread(
                        target=_run_scraper, args=(retailer, request_id), daemon=True
                    )
                    thread.start()
                    st.info("Scraper started in background. Check Run History tab for progress.")
                else:
                    st.warning(
                        "Chrome is not available on this machine. "
                        "The run has been queued in MongoDB (`scrape_requests` collection). "
                        "Use the Docker container to process it:\n\n"
                        "```bash\n"
                        "docker-compose run scraper\n"
                        "```"
                    )
                time.sleep(1)
                st.rerun()

        with col2:
            st.markdown("#### Quick Run Options")
            st.markdown("- **Both retailers** (default) — scrapes Aldi then Sainsbury's")
            st.markdown("- **Single retailer** — scrapes only the selected retailer")
            st.markdown("- Runs are tracked in MongoDB with per-category timing")

    with tab2:
        st.markdown("### Schedule Configuration")

        st.info(
            "Scheduling is configured via environment or cron. "
            "The recommended approach is to set up a systemd timer or cron job "
            "that runs the Docker container at your desired intervals."
        )

        st.markdown("#### Recommended Schedule")
        schedule_df = pd.DataFrame([
            {"Run": "Morning", "Time": "06:00 UTC", "Retailer": "all",
             "Command": "docker-compose run scraper"},
            {"Run": "Evening", "Time": "18:00 UTC", "Retailer": "all",
             "Command": "docker-compose run scraper"},
        ])
        st.dataframe(schedule_df, use_container_width=True, hide_index=True)

        st.markdown("#### Cron Setup")
        st.code(
            "# Run twice daily (6 AM and 6 PM UTC)\n"
            "0 6,18 * * * cd /path/to/SmartShop && docker-compose run scraper\n\n"
            "# Or with specific retailer\n"
            "0 6 * * * cd /path/to/SmartShop && RETAILER=aldi docker-compose run scraper\n"
            "0 18 * * * cd /path/to/SmartShop && RETAILER=sainsburys docker-compose run scraper",
            language="bash"
        )

        st.markdown("#### Schedule Jobs")
        db = get_db()
        schedules = list(db["performance_metrics"].find({"type": "schedule"}).sort("created_at", -1))
        if schedules:
            rows = []
            for s in schedules:
                rows.append({
                    "Retailer": s.get("retailer", "all"),
                    "Cron Expression": s.get("cron", "-"),
                    "Created": str(s.get("created_at", ""))[:19],
                    "Active": "Yes" if s.get("active") else "No",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No schedules configured. Use cron on your server (see above).")

    with tab3:
        st.markdown("### Run History")
        runs = get_queued_runs()
        if runs:
            rows = []
            for r in runs:
                rows.append({
                    "Time": str(r.get("created_at", ""))[:19],
                    "Retailer": r.get("retailer", ""),
                    "Status": r.get("status", ""),
                    "Started": str(r.get("started_at", ""))[:19] if r.get("started_at") else "-",
                    "Completed": str(r.get("completed_at", ""))[:19] if r.get("completed_at") else "-",
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            selected = st.selectbox("View details", options=range(len(runs)),
                                    format_func=lambda i: f"Run {i+1}: {runs[i].get('status', '?')}")
            if runs[selected].get("output"):
                with st.expander("Output"):
                    st.code(runs[selected]["output"][-3000:])
            if runs[selected].get("errors"):
                with st.expander("Errors"):
                    st.code(runs[selected]["errors"][-3000:])
        else:
            st.info("No runs have been queued yet")
