import streamlit as st
import pandas as pd
import time
import os
from datetime import datetime, timezone
from utils import (
    get_db, get_queued_runs, queue_scrape_run, update_queue_status, can_run_scraper,
    get_active_request, get_scrape_logs, start_scraper_thread, ensure_aware
)


def show():
    st.subheader("Scraper Control")

    # ── Live Progress Section ──
    active = get_active_request()
    if active:
        status = active.get("status", "?")
        rid = str(active.get("_id"))
        retailer = active.get("retailer", "?")

        if status == "running":
            st.markdown("###  Active Scraping Run")
            col1, col2, col3 = st.columns(3)
            col1.metric("Status", "Running", delta="In Progress")
            col2.metric("Retailer", retailer)
            started = active.get("started_at")
            if started:
                started = ensure_aware(started)
                elapsed = (datetime.now(timezone.utc) - started).total_seconds()
                col3.metric("Elapsed", f"{elapsed:.0f}s")

            st.progress(0.5, text="Scraping in progress...")

            logs = get_scrape_logs(rid)
            if logs:
                with st.expander("Live Logs", expanded=True):
                    log_text = "\n".join(logs[-50:])
                    st.code(log_text, language="bash")

            st.markdown("---")
            if st.button(" Refresh Status"):
                st.rerun()

            time.sleep(3)
            st.rerun()

        elif status == "queued":
            st.info(f" Run for **{retailer}** is queued — waiting for a worker to pick it up.")
            if st.button(" Check Status"):
                st.rerun()
            time.sleep(3)
            st.rerun()

    # ── Tabs ──
    tab1, tab2, tab3 = st.tabs(["Start Scraping", "Schedule", "Run Queue"])

    with tab1:
        st.markdown("### Start a Scraping Run")

        retailer = st.radio("Select retailer", ["all", "aldi", "sainsburys"],
                            format_func=lambda x: {"all": "Both Retailers", "aldi": "Aldi",
                                                   "sainsburys": "Sainbury's"}[x],
                            horizontal=True, key="ctrl_retailer")

        chrome_ok, chrome_path = can_run_scraper()

        # Detect Streamlit Cloud (no Chrome available, no local scraping)
        on_cloud = os.environ.get("STREAMLIT_RUN_ON_SAVE") is not None

        if on_cloud:
            st.info(
                "  **Streamlit Cloud detected.** Scraping requires Chrome/Chromium "
                "and cannot run here. Use the Docker container locally:\n\n"
                "```bash\n"
                "export MONGO_URI='your_atlas_uri'\n"
                "docker compose up admin\n"
                "```"
            )
        if chrome_ok:
            st.success(f" Chrome detected: {chrome_path}")
        else:
            st.warning(
                "Chrome/Chromium is not installed on this machine. "
                "Scraping will be queued for the Docker container.\n\n"
                "To run locally, install Chrome:\n"
                "```bash\nbrew install --cask google-chrome\n```"
            )

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button(" Start Scraping Now", type="primary", use_container_width=True):
                request_id = queue_scrape_run(retailer)
                if request_id:
                    if chrome_ok:
                        st.success(f"Starting scraper for {retailer}...")
                        start_scraper_thread(request_id, retailer)
                        st.info("Scroll up to see live progress above.")
                    else:
                        st.info(
                            f"Run queued (ID: {request_id[:8]}...). "
                            "Use the Docker container to process:\n\n"
                            "```bash\nMONGO_URI=... docker-compose run scraper\n```"
                        )
                else:
                    st.error("Failed to queue run")
                time.sleep(2)
                st.rerun()

        with col2:
            st.markdown("**Quick Info**")
            st.markdown("- Full scrape: ~5-15 minutes per retailer")
            st.markdown("- Skips previously scraped categories")
            st.markdown("- Per-category timing recorded in MongoDB")
            st.markdown("- Live logs appear above while running")

    with tab2:
        st.markdown("### Schedule Configuration")

        st.info(
            "Scheduling is handled via cron/systemd on your server. "
            "The Docker container runs the scraper; a cron job triggers it at set intervals."
        )

        st.markdown("#### Recommended Schedule (Twice Daily)")
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
            "# Run Aldi in morning, Sainbury's in evening\n"
            "0 6 * * * cd /path/to/SmartShop && RETAILER=aldi docker-compose run scraper\n"
            "0 18 * * * cd /path/to/SmartShop && RETAILER=sainsburys docker-compose run scraper",
            language="bash"
        )

    with tab3:
        st.markdown("### Run Queue History")
        runs = get_queued_runs(100)
        if runs:
            rows = []
            status_colors = {"queued": " ", "running": " ", "completed": " ✅",
                             "failed": " ❌", "timeout": " ⏰"}
            for r in runs:
                s = r.get("status", "?")
                icon = status_colors.get(s, " ❓")
                rows.append({
                    "ID": str(r.get("_id"))[:8],
                    "Time": str(r.get("created_at", ""))[:19],
                    "Retailer": r.get("retailer", ""),
                    "Status": f"{icon} {s}",
                    "Started": str(r.get("started_at", ""))[:19] if r.get("started_at") else "-",
                    "Completed": str(r.get("completed_at", ""))[:19] if r.get("completed_at") else "-",
                    "_log": r.get("log", []),
                })
            df = pd.DataFrame(rows)

            display_cols = ["Time", "Retailer", "Status", "Started", "Completed"]
            st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

            selected_idx = st.selectbox(
                "View run logs",
                options=range(len(rows)),
                format_func=lambda i: f"{rows[i]['ID']} — {rows[i]['Retailer']} — {rows[i]['Status']}",
                key="queue_log_select"
            )
            selected = rows[selected_idx]
            logs = selected.get("_log", [])
            if logs:
                with st.expander(f"Logs for run {selected['ID']}", expanded=True):
                    st.code("\n".join(logs[-200:]), language="bash")
            else:
                st.info("No logs for this run (may still be queued or logs not captured)")
        else:
            st.info("No runs have been queued yet")
