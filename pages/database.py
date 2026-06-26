import streamlit as st
import pandas as pd
from utils import get_dashboard_overview


def show():
    data = get_dashboard_overview()
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
            df = pd.DataFrame(consumer)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No consumer collections")

    with tab2:
        if internal:
            df = pd.DataFrame(internal)
            st.dataframe(df, use_container_width=True, hide_index=True)
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
