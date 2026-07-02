import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from utils import get_scraping_runs, get_run_detail


def show():
    if "run_page" not in st.session_state:
        st.session_state.run_page = 1
    if "run_detail_id" not in st.session_state:
        st.session_state.run_detail_id = None

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        date_from = st.date_input("From", value=None, key="rf_from")
    with col2:
        date_to = st.date_input("To", value=None, key="rf_to")
    with col3:
        retailer = st.selectbox("Retailer", ["", "aldi", "sainsburys"], key="rf_ret")
    with col4:
        status = st.selectbox("Status", ["", "completed", "failed"], key="rf_stat")

    df_val = None
    if date_from:
        df_val = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
    dt_val = None
    if date_to:
        dt_val = datetime.combine(date_to, datetime.min.time()).replace(tzinfo=timezone.utc)

    per_page = 15
    runs, total = get_scraping_runs(df_val, dt_val, retailer or None, status or None,
                                    st.session_state.run_page, per_page)
    total_pages = max(1, (total + per_page - 1) // per_page)

    if runs:
        rows = []
        for r in runs:
            rows.append({
                "Time": str(r.get("timestamp", ""))[:19],
                "Retailer": r.get("retailer", ""),
                "Status": r.get("status", ""),
                "Categories OK": r.get("categories_success", 0),
                "Failed": r.get("categories_failed", 0),
                "Products": r.get("products_total", 0),
                "Duration": f'{r.get("duration_seconds", 0):.1f}s',
                "_id": r.get("_id", ""),
            })
        df = pd.DataFrame(rows)
        display_df = df.drop(columns=["_id"])
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        col_prev, col_info, col_next = st.columns([1, 2, 1])
        with col_prev:
            if st.button("← Previous", disabled=(st.session_state.run_page <= 1)):
                st.session_state.run_page -= 1
                st.rerun()
        with col_info:
            st.markdown(f"<div style='text-align:center;color:#94a3b8'>Page {st.session_state.run_page} of {total_pages} ({total} runs)</div>",
                        unsafe_allow_html=True)
        with col_next:
            if st.button("Next →", disabled=(st.session_state.run_page >= total_pages)):
                st.session_state.run_page += 1
                st.rerun()

        selected_id = st.selectbox("View run details", options=df["_id"].tolist(),
                                   format_func=lambda x: f"Run {str(x)[:8]}...")
        if st.button("Show Details"):
            st.session_state.run_detail_id = selected_id
            st.rerun()
    else:
        st.info("No scraping runs found")

    if st.session_state.run_detail_id:
        with st.expander("Run Detail", expanded=True):
            detail = get_run_detail(st.session_state.run_detail_id)
            if "error" in detail:
                st.error(detail["error"])
            else:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Retailer", detail.get("retailer", "-"))
                c2.metric("Status", detail.get("status", "-"))
                c3.metric("Products", detail.get("products_total", 0))
                c4.metric("Duration", f'{detail.get("duration_seconds", 0):.1f}s')

                cats = detail.get("categories", [])
                if cats:
                    cat_rows = []
                    for c in sorted(cats, key=lambda x: x.get("duration_seconds", 0), reverse=True):
                        cat_rows.append({
                            "Category": c.get("category", ""),
                            "Products": c.get("product_count", 0),
                            "Duration": f'{c.get("duration_seconds", 0):.1f}s',
                            "Status": c.get("status", ""),
                        })
                    st.dataframe(pd.DataFrame(cat_rows), use_container_width=True, hide_index=True)
                    if cat_rows:
                        import plotly.express as px
                        cdf = pd.DataFrame(cat_rows)
                        cdf["DurationSec"] = [c.get("duration_seconds", 0) for c in cats]
                        fig = px.bar(cdf.head(20), x="Category", y="DurationSec",
                                     title="Top 20 Categories by Duration",
                                     labels={"DurationSec": "Duration (s)"})
                        st.plotly_chart(fig, use_container_width=True)

            if st.button("Close Details"):
                st.session_state.run_detail_id = None
                st.rerun()
