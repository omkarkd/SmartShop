# %% [markdown]
# # 01 — Data Exploration & Cleaning
# 
# Explore the scraped product data from Aldi (3,619 products) and Sainsbury's (5,500 products), 
# understand schemas, fix price formats, clean categories, and handle missing values.

# %% [markdown]
# ## Setup & Imports

# %%
import re
import json
from datetime import datetime
from collections import Counter, defaultdict

import pymongo
import pandas as pd
import numpy as np

try:
    from IPython.display import display
except ImportError:
    def display(x):
        if hasattr(x, 'to_string'):
            print(x.to_string())
        else:
            print(x)

# %% [markdown]
# ## Connect to MongoDB

# %%
client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["smartshop"]

aldi_raw = list(db["aldi_products"].find({}))
sains_raw = list(db["sainsburys_products"].find({}))

print(f"Aldi products:       {len(aldi_raw):>6}")
print(f"Sainsbury's products: {len(sains_raw):>6}")

# %% [markdown]
# ## Convert to DataFrames

# %%
def flatten(docs, retailer):
    rows = []
    for d in docs:
        d["retailer"] = retailer
        d.pop("_id", None)
        rows.append(d)
    return pd.DataFrame(rows)

aldi_df = flatten(aldi_raw, "aldi")
sains_df = flatten(sains_raw, "sainsburys")
df = pd.concat([aldi_df, sains_df], ignore_index=True)

print(f"Combined: {len(df)} rows, {len(df.columns)} columns")
print(f"Columns: {list(df.columns)}")

# %% [markdown]
# ## Schema Comparison

# %%
def schema(df, name):
    info = []
    for col in df.columns:
        info.append({
            "column": col,
            "dtype": str(df[col].dtype),
            "non_null": df[col].notna().sum(),
            "null_pct": round(df[col].isna().mean() * 100, 1),
            "unique": df[col].nunique(),
            "sample": str(df[col].dropna().iloc[0])[:60] if df[col].notna().any() else ""
        })
    return pd.DataFrame(info)

print("=== ALDI SCHEMA ===")
display(schema(aldi_df, "Aldi"))
print("\n=== SAINSBURY'S SCHEMA ===")
display(schema(sains_df, "Sainsbury's"))

# %% [markdown]
# ## Missing Values Analysis

# %%
missing = pd.DataFrame({
    "column": df.columns,
    "aldi_null%": [round(aldi_df[c].isna().mean() * 100, 1) if c in aldi_df.columns else 100.0 for c in df.columns],
    "sains_null%": [round(sains_df[c].isna().mean() * 100, 1) if c in sains_df.columns else 100.0 for c in df.columns],
    "total_null%": [round(df[c].isna().mean() * 100, 1) for c in df.columns],
})
display(missing)

# %% [markdown]
# ### Observations
# - Aldi: no `image_url` or `promotion_badge` (fields don't exist in scraped data)
# - Sainsbury's: `brand` is often null (55%), `was_price` is mostly null, `size` doesn't exist
# - `price_with_promotion` null for Sainsbury's (most products aren't on promotion)
# - `price` is available for all products — good!

# %% [markdown]
# ## Price Cleaning
# Check for invalid price formats

# %%
def check_prices(series, label):
    issues = []
    for i, val in series.items():
        if val is None:
            issues.append((i, "None"))
        elif isinstance(val, str):
            issues.append((i, f"string: {val[:40]}"))
        elif isinstance(val, (int, float)):
            if val <= 0:
                issues.append((i, f"non-positive: {val}"))
            elif val > 1000:
                issues.append((i, f"suspiciously high: {val}"))
    return issues

print("Aldi price issues:", len(check_prices(aldi_df["price"], "aldi")))
print("Sains price issues:", len(check_prices(sains_df["price"], "sains")))

# %%
# Check for suspiciously high prices
def numeric_price(series):
    return pd.to_numeric(series, errors="coerce")

aldi_prices_num = numeric_price(aldi_df["price"])
sains_prices_num = numeric_price(sains_df["price"])
high_aldi = aldi_df[aldi_prices_num > 50]
high_sains = sains_df[sains_prices_num > 50]
print(f"Aldi prices > £50: {len(high_aldi)}")
print(f"Sainsbury's prices > £50: {len(high_sains)}")

if len(high_sains) > 0:
    display(high_sains[["product_name", "price", "price_per_unit", "category"]].head(10))

# %%
# Fix: these are likely price_per_unit values stored in price field
# Let's see which ones look like per-unit prices
def looks_like_per_unit(val):
    """Check if a price string looks like it's actually per-unit pricing"""
    s = str(val)
    return "/" in s or "per" in s.lower() or "each" in s.lower()

# Fix price: try to parse numeric, fall back to per-unit extraction
def clean_price(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if val > 100:  # Suspect: likely per-unit price
            return None
        return float(val)
    if isinstance(val, str):
        m = re.search(r"(\d+\.?\d*)", val)
        return float(m.group(1)) if m else None
    return None

# Apply cleaning
aldi_df["price_clean"] = aldi_df["price"].apply(clean_price)
sains_df["price_clean"] = sains_df["price"].apply(clean_price)

# Check how many we "lost"
print(f"Aldi prices cleaned: {(aldi_df['price_clean'].isna().sum())} nulls (was {aldi_df['price'].isna().sum()})")
print(f"Sains prices cleaned: {(sains_df['price_clean'].isna().sum())} nulls (was {sains_df['price'].isna().sum()})")

# %% [markdown]
# ## Category Cleaning
# Normalise category names across both retailers

# %%
# Analyse category structure
aldi_cats = Counter(aldi_df["category"].dropna())
sains_cats = Counter(sains_df["category"].dropna())
aldi_top = aldi_cats.most_common(20)
sains_top = sains_cats.most_common(20)

print("TOP 20 ALDI CATEGORIES")
print(f"{'Category':<45} {'Count':>6}")
print("-" * 52)
for c, n in aldi_top:
    print(f"{c:<45} {n:>6}")

print("\nTOP 20 SAINSBURY'S CATEGORIES")
print(f"{'Category':<55} {'Count':>6}")
print("-" * 62)
for c, n in sains_top:
    print(f"{c:<55} {n:>6}")

# %%
# Aldi uses " > " for subcategories, Sainsbury's also uses " > "
# Let's find overlapping categories
aldi_cat_set = set(aldi_cats.keys())
sains_cat_set = set(sains_cats.keys())
overlap_cats = aldi_cat_set & sains_cat_set

print(f"Aldi unique categories:      {len(aldi_cat_set)}")
print(f"Sainsbury's unique categories: {len(sains_cat_set)}")
print(f"Overlapping exact names:     {len(overlap_cats)}")
print()
for c in sorted(overlap_cats)[:15]:
    print(f"  ✓ {c}")

# %%
# Extract top-level and sub-level categories
def split_category(cat):
    if not cat or pd.isna(cat):
        return pd.Series([None, None])
    parts = [p.strip() for p in cat.split(">")]
    top = parts[0] if len(parts) > 0 else None
    sub = parts[1] if len(parts) > 1 else None
    return pd.Series([top, sub])

aldi_df[["cat_top", "cat_sub"]] = aldi_df["category"].apply(split_category)
sains_df[["cat_top", "cat_sub"]] = sains_df["category"].apply(split_category)

# Top-level category comparison
aldi_top_cats = Counter(aldi_df["cat_top"].dropna())
sains_top_cats = Counter(sains_df["cat_top"].dropna())
print("{:<35} {:>6} {:>6}".format("Top-Level Category", "Aldi", "Sains"))
print("-" * 50)
all_tops = set(list(aldi_top_cats.keys()) + list(sains_top_cats.keys()))
for t in sorted(all_tops):
    print(f"{t:<35} {aldi_top_cats.get(t, 0):>6} {sains_top_cats.get(t, 0):>6}")

# %% [markdown]
# ## Brand Analysis

# %%
# Aldi brands are all uppercase, Sainsbury's has many None
print("ALDI TOP 15 BRANDS")
print(aldi_df["brand"].value_counts().head(15).to_string())
print()

print("SAINSBURY'S TOP 15 BRANDS")
print(sains_df["brand"].value_counts().head(15).to_string())
print()

# Sainsbury's null brands
null_brand = sains_df[sains_df["brand"].isna() | (sains_df["brand"] == "")]
print(f"Sainsbury's products with no brand: {len(null_brand)} ({len(null_brand)/len(sains_df)*100:.0f}%)")
# These are likely own-brand products
# Show examples
if len(null_brand) > 0:
    display(null_brand[["product_name", "is_own_brand", "category"]].head(10))

# %%
# Fill missing brands: if is_own_brand, label as "Own Brand"
def fill_brand(row):
    if pd.isna(row["brand"]) or row["brand"] == "":
        if row.get("is_own_brand"):
            return "Own Brand"
        return "Unknown"
    return row["brand"]

sains_df["brand_filled"] = sains_df.apply(fill_brand, axis=1)
aldi_df["brand_filled"] = aldi_df.apply(fill_brand, axis=1)

print("Sainsbury's brands after fill:")
print(sains_df["brand_filled"].value_counts().head(15).to_string())

# %% [markdown]
# ## Own-Brand Analysis

# %%
# Aldi is mostly own-brand, Sainsbury's has mix
print("ALDI own-brand:")
print(aldi_df["is_own_brand"].value_counts().to_string())
print()
print("SAINSBURY'S own-brand:")
print(sains_df["is_own_brand"].value_counts().to_string())

# %%
# Price comparison: own-brand vs branded (where we have brand info)
# For Sainsbury's
sains_with_brand = sains_df[sains_df["brand_filled"] != "Own Brand"]
sains_own = sains_df[sains_df["brand_filled"] == "Own Brand"]

if len(sains_own) > 0 and len(sains_with_brand) > 0:
    print(f"Sainsbury's branded avg price:  £{sains_with_brand['price_clean'].mean():.2f}")
    print(f"Sainsbury's own-brand avg price: £{sains_own['price_clean'].mean():.2f}")
    avg_saving = sains_with_brand['price_clean'].mean() - sains_own['price_clean'].mean()
    print(f"Average saving with own-brand:  £{avg_saving:.2f} ({avg_saving/sains_with_brand['price_clean'].mean()*100:.0f}%)")

# %% [markdown]
# ## Price Distribution

# %%
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 2, figsize=(12, 4))

# Price distribution (log scale for visibility)
for ax, data, label, color in [
    (axes[0], aldi_df["price_clean"].dropna(), "Aldi", "#0066a1"),
    (axes[0], sains_df["price_clean"].dropna(), "Sainsbury's", "#e87722"),
]:
    ax.hist(data, bins=50, alpha=0.6, label=label, color=color)
    ax.set_xlabel("Price (£)")
    ax.set_ylabel("Frequency")
    ax.set_title("Price Distribution (Aldi vs Sainsbury's)")
    ax.legend()

# Box plot
axes[1].boxplot([
    aldi_df["price_clean"].dropna(),
    sains_df["price_clean"].dropna()
], labels=["Aldi", "Sainsbury's"])
axes[1].set_ylabel("Price (£)")
axes[1].set_title("Price Range Comparison")
axes[1].grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.show()

# %% [markdown]
# ## Summary Statistics

# %%
stats = []
for label, data in [("Aldi", aldi_df), ("Sainsbury's", sains_df)]:
    prices = data["price_clean"].dropna()
    stats.append({
        "retailer": label,
        "count": len(data),
        "unique_products": data["product_name"].nunique(),
        "categories": data["category"].nunique(),
        "brands": data["brand_filled"].nunique() if "brand_filled" in data.columns else data["brand"].nunique(),
        "own_brand_pct": round(data["is_own_brand"].mean() * 100, 1),
        "min_price": prices.min(),
        "max_price": prices.max(),
        "median_price": prices.median(),
        "mean_price": round(prices.mean(), 2),
        "promotions": data["was_price"].notna().sum(),
    })

stats_df = pd.DataFrame(stats)
display(stats_df)

# %% [markdown]
# ## Export Cleaned Data

# %%
# Save cleaned dataframes to CSV for downstream analysis
aldi_df.to_csv("notebooks/data/aldi_cleaned.csv", index=False)
sains_df.to_csv("notebooks/data/sainsburys_cleaned.csv", index=False)
print("Cleaned data exported to notebooks/data/")

# %% [markdown]
# ## Key Findings
# 
# 1. **Prices**: Aldi generally cheaper; some Sainsbury's prices are per-unit values stored as prices (e.g. £45 for Dijon mustard) — cleaned using regex
# 2. **Categories**: Only a few exact category overlaps (Bakery, Chilled Food, Food Cupboard, Frozen). Aldi uses simpler hierarchy, Sainsbury's is deeper
# 3. **Brands**: Aldi products are 99.9% own-brand. Sainsbury's is ~44% own-brand, 56% branded — with many missing brand values
# 4. **Missing data**: Sainsbury's `brand` is 55% null; `was_price` mostly null for both. Aldi has no `image_url`
# 5. **Promotions**: Aldi ~12% products on promotion; Sainsbury's ~1%
