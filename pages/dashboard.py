import streamlit as st
import pandas as pd
from utils import get_dashboard_overview


def show():
    data = get_dashboard_overview()

    today_cats = data.get("today_category_stats", [])
    total_cat_ok = sum(r.get("categories_success", 0) for r in today_cats)
    total_cat_fail = sum(r.get("categories_failed", 0) for r in today_cats)
    total_products_today = sum(r.get("total_products_found", 0) for r in today_cats)
    today_runs = data.get("today_runs", 0)
    db_stats = data.get("db_stats", {})

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        st.metric("Today's Runs", today_runs)
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        st.metric("Today's Products", total_products_today)
        st.markdown('</div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        st.metric("Categories Today", f"{total_cat_ok} / {total_cat_fail} fail")
        st.markdown('</div>', unsafe_allow_html=True)
    with col4:
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        st.metric("Database Size", db_stats.get("total_size", "-"))
        st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("Today's Scraping Activity", expanded=True):
        if today_cats:
            rows = []
            for r in today_cats:
                rows.append({
                    "Retailer": r.get("_id", "?"),
                    "Categories OK": r.get("categories_success", 0),
                    "Failed": r.get("categories_failed", 0),
                    "Products Found": r.get("total_products_found", 0),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No scraping activity today")

    with st.expander("Scraper Run History", expanded=True):
        summary = data.get("scraper_summary", [])
        if summary:
            rows = []
            for r in summary:
                rows.append({
                    "Retailer": r["_id"],
                    "Last Run": str(r.get("last_run", "-"))[:19],
                    "Status": r.get("last_status", "-"),
                    "Products": r.get("last_products", 0),
                    "Avg Products": int(r.get("avg_products", 0)),
                    "Total Runs": r.get("total_runs", 0),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No scraper runs recorded yet")

    with st.expander("Collections Overview", expanded=True):
        cols = data.get("collections", [])
        if cols:
            df = pd.DataFrame(cols)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No collection data")
