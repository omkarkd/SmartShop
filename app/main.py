
# import streamlit as st
# import pandas as pd

# # 1. Load your data
# @st.cache_data
# def load_data():
#     df = pd.read_csv("/Users/omkar/Documents/SmartShop/app/food_cupboard.csv") # or pd.read_excel
#     # CRITICAL: Convert date column to actual datetime objects
#     df['date'] = pd.to_datetime(df['date'])
#     return df

# df = load_data()

# st.title("🛒 SmartShop Price Finder")

# # 2. Search Bar
# search_query = st.text_input("What are you looking for?", placeholder="e.g. coffee")

# if search_query:
#     # 3. Filter by name (case-insensitive)
#     mask = df['names'].str.contains(search_query, case=False, na=False)
#     filtered_df = df[mask]

#     if not filtered_df.empty:
#         # 4. Logic to find the LATEST price for each product at each supermarket
#         # We group by supermarket and name, then find the index of the max date
#         latest_indices = filtered_df.groupby(['supermarket', 'names'])['date'].idxmax()
#         latest_prices = filtered_df.loc[latest_indices]

#         # 5. Final Selection of requested columns
#         display_cols = ['supermarket', 'names', 'prices_(£)', 'date', 'own_brand']
#         final_view = latest_prices[display_cols].sort_values(by='prices_(£)')

#         st.subheader(f"Latest prices for '{search_query}'")
#         st.dataframe(
#             final_view, 
#             column_config={
#                 "date": st.column_config.DateColumn("Last Updated"),
#                 "prices_(£)": st.column_config.NumberColumn("Price", format="£%.2f")
#             },
#             hide_index=True,
#             use_container_width=True
#         )
#     else:
#         st.warning("No products found.")
# else:
#     st.info("Enter a product name above to see the best current deals across retailers.")


import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os

# 1. Flexible Data Loading
@st.cache_data
def load_data():
    # Path to the folder containing all your supermarket CSVs
    path = "/Users/omkar/Documents/SmartShop/app/" 
    
    # This finds all CSV files in that folder
    all_files = glob.glob(os.path.join(path, "*.csv"))
    
    li = []
    for filename in all_files:
        # Read each file and add a 'source_file' column just in case
        df_temp = pd.read_csv(filename)
        li.append(df_temp)

    # Combine all CSVs into one big DataFrame
    df = pd.concat(li, axis=0, ignore_index=True)
    
    # Standardize date and cleaning
    df['date'] = pd.to_datetime(df['date'])
    # Optional: ensure prices are numeric
    df['prices_(£)'] = pd.to_numeric(df['prices_(£)'], errors='coerce')
    
    return df

df = load_data()

# --- Sidebar Navigation ---
st.sidebar.title("🛒 SmartShop Admin")
page = st.sidebar.radio("Navigation", ["Price Finder", "Price History Trends"])

# --- SHARED FILTERS (Applicable to both pages) ---
st.sidebar.divider()
st.sidebar.subheader("Global Filters")

# Filter by Retailer (Dynamically populated from your files)
retailer_list = ["All"] + list(df['supermarket'].unique())
selected_retailer = st.sidebar.multiselect("Select Retailers", retailer_list, default="All")

# Filter by Brand Type
brand_type = st.sidebar.selectbox("Brand Category", ["All", "Own Brand", "3rd Party"])

# Apply sidebar filters to a working dataframe
df_filtered = df.copy()

if "All" not in selected_retailer:
    df_filtered = df_filtered[df_filtered['supermarket'].isin(selected_retailer)]

if brand_type == "Own Brand":
    df_filtered = df_filtered[df_filtered['own_brand'] == True]
elif brand_type == "3rd Party":
    df_filtered = df_filtered[df_filtered['own_brand'] == False]


# --- Page 1: Price Finder ---
if page == "Price Finder":
    st.title("🔎 Price Comparison Search")
    search_query = st.text_input("Search for a brand or product (e.g., Shan, Garnier, Milk)")

    if search_query:
        mask = df_filtered['names'].str.contains(search_query, case=False, na=False)
        results = df_filtered[mask]

        if not results.empty:
            # Get latest price for each product at each store
            latest_idx = results.groupby(['supermarket', 'names'])['date'].idxmax()
            final_view = results.loc[latest_idx].sort_values(by='prices_(£)')

            st.dataframe(
                final_view[['supermarket', 'names', 'prices_(£)', 'date']], 
                column_config={
                    "date": st.column_config.DateColumn("Date Updated"),
                    "prices_(£)": st.column_config.NumberColumn("Price", format="£%.2f")
                },
                hide_index=True, use_container_width=True
            )
        else:
            st.warning("No matches found in the current datasets.")

# --- Page 2: Price History Trends ---
elif page == "Price History Trends":
    st.title("📈 Historical Analysis")
    
    # Dynamically list products based on previous filters
    product_options = sorted(df_filtered['names'].unique())
    target_product = st.selectbox("Select product to track:", product_options)

    if target_product:
        plot_df = df_filtered[df_filtered['names'] == target_product].sort_values('date')

        # Time Slider
        min_d, max_d = plot_df['date'].min().to_pydatetime(), plot_df['date'].max().to_pydatetime()
        timerange = st.slider("Timeline", min_value=min_d, max_value=max_d, value=(min_d, max_d))

        # Filter plot data by time
        plot_df = plot_df[(plot_df['date'] >= timerange[0]) & (plot_df['date'] <= timerange[1])]

        fig = px.line(
            plot_df, x='date', y='prices_(£)', color='supermarket',
            markers=True, title=f"Price Fluctuation: {target_product}",
            labels={"prices_(£)": "Price (£)"}
        )
        st.plotly_chart(fig, use_container_width=True)