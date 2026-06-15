import streamlit as st
from utils import search_products  # or keep in same file



@st.cache_data
def cached_search(query, min_q, max_q, unit):
    return search_products(query, min_q, max_q, unit)


st.title("🛒 Retail Price Comparison")

query = st.text_input("Search product")

col1, col2, col3 = st.columns(3)

with col1:
    unit = st.selectbox("Unit", ["", "g", "ml"])

with col2:
    min_q = st.number_input("Min Qty", value=0)

with col3:
    max_q = st.number_input("Max Qty", value=2000)

if query:
    df = search_products(query, min_q, max_q, unit)
    st.dataframe(df)