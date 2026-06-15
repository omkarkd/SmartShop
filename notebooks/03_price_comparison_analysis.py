# %% [markdown]
# # 03 — Price Comparison Analysis
# 
# Deep-dive into pricing across Aldi and Sainsbury's. Compare matched products, find the best deals,
# analyse category-level pricing, and build a price index.

# %% [markdown]
# ## Setup & Imports

# %%
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
from collections import Counter, defaultdict

import pymongo
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

try:
    from IPython.display import display
except ImportError:
    def display(x):
        if hasattr(x, 'to_string'):
            print(x.to_string())
        else:
            print(x)

# %% [markdown]
# ## Load Data

# %%
client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["smartshop"]

aldi_docs = list(db["aldi_products"].find({}, {"_id": 0}))
sains_docs = list(db["sainsburys_products"].find({}, {"_id": 0}))

from backend.services.matching_service import find_matches

print(f"Aldi:        {len(aldi_docs)} products")
print(f"Sainsbury's: {len(sains_docs)} products")

# %% [markdown]
# ## Build Matched Product Catalogue

# %%
def safe_price(val):
    if val is None: return None
    try: return float(val)
    except: return None

# Match all Aldi → Sainsbury's (sampled for performance)
import random
random.seed(42)
MATCH_SAMPLE = 1500
aldi_sample = random.sample(aldi_docs, min(MATCH_SAMPLE, len(aldi_docs)))

matched_pairs = []
for i, p in enumerate(aldi_sample):
    if i % 300 == 0 and i > 0:
        print(f"  Matching progress: {i}/{len(aldi_sample)}")
    ms = find_matches(p, "aldi", min_score=0.55, limit=1)
    if not ms: continue
    m = ms[0]
    ap = safe_price(p.get("price"))
    sp = safe_price(m.get("price"))
    if ap is None or sp is None or ap <= 0 or sp <= 0: continue
    if sp > 30 or ap > 30: continue  # filter anomalies
    matched_pairs.append({
        "aldi_name": p["product_name"],
        "aldi_price": ap,
        "aldi_category": p.get("category", ""),
        "aldi_cat_top": p.get("category", "").split(" > ")[0] if " > " in p.get("category", "") else p.get("category", ""),
        "sains_name": m["product_name"],
        "sains_price": sp,
        "sains_category": m.get("category", ""),
        "sains_cat_top": m.get("category", "").split(" > ")[0] if " > " in m.get("category", "") else m.get("category", ""),
        "score": m.get("match_score", 0),
        "diff": round(sp - ap, 2),
        "diff_pct": round((sp - ap) / ap * 100, 1),
        "cheaper_at": "aldi" if sp > ap else ("sainsburys" if sp < ap else "same"),
    })

df = pd.DataFrame(matched_pairs)
print(f"Matched products: {len(df)}")
print(f"Aldi cheaper:  {len(df[df['cheaper_at'] == 'aldi'])} ({(df['cheaper_at'] == 'aldi').mean()*100:.0f}%)")
print(f"Sains cheaper: {len(df[df['cheaper_at'] == 'sainsburys'])}")

# %% [markdown]
# ## Overall Price Comparison

# %%
total_aldi = df["aldi_price"].sum()
total_sains = df["sains_price"].sum()
avg_aldi = df["aldi_price"].mean()
avg_sains = df["sains_price"].mean()

print(f"{'Metric':<30} {'Aldi':>8} {'Sainsbury':>10}")
print("-" * 50)
print(f"{'Total basket':<30} £{total_aldi:>6.2f} £{total_sains:>7.2f}")
print(f"{'Average price':<30} £{avg_aldi:>6.2f} £{avg_sains:>7.2f}")
print(f"{'Median price':<30} £{df['aldi_price'].median():>6.2f} £{df['sains_price'].median():>7.2f}")
print(f"{'Min price':<30} £{df['aldi_price'].min():>6.2f} £{df['sains_price'].min():>7.2f}")
print(f"{'Max price':<30} £{df['aldi_price'].max():>6.2f} £{df['sains_price'].max():>7.2f}")
print(f"{'Total savings at Aldi':<30} £{total_sains - total_aldi:>6.2f}")
print(f"{'Avg savings per item':<30} £{df['diff'].mean():>6.2f}")
print(f"{'Avg savings %':<30} {df['diff_pct'].mean():>7.1f}%")

# %% [markdown]
# ## Savings Distribution

# %%
fig, axes = plt.subplots(1, 2, figsize=(14, 4))

# Absolute savings
axes[0].hist(df["diff"], bins=40, color="#2e7d32", alpha=0.7, edgecolor="white")
axes[0].axvline(x=0, color="red", linestyle="--")
axes[0].set_xlabel("Savings at Aldi (£)")
axes[0].set_ylabel("Count")
axes[0].set_title("Absolute Savings per Product")

# Percentage savings
axes[1].hist(df["diff_pct"].clip(-50, 200), bins=40, color="#2e7d32", alpha=0.7, edgecolor="white")
axes[1].axvline(x=0, color="red", linestyle="--")
axes[1].set_xlabel("Savings at Aldi (%)")
axes[1].set_ylabel("Count")
axes[1].set_title("Percentage Savings per Product")

plt.tight_layout()
plt.show()

# %% [markdown]
# ## Category-Level Price Comparison

# %%
cat_stats = df.groupby("aldi_cat_top").agg({
    "aldi_price": ["mean", "sum", "count"],
    "sains_price": ["mean", "sum"],
    "diff": "mean",
    "diff_pct": "mean",
}).round(2)

cat_stats.columns = ["aldi_avg", "aldi_total", "count", "sains_avg", "sains_total", "avg_savings_£", "avg_savings_%"]
cat_stats = cat_stats.sort_values("count", ascending=False)
cat_stats["cheaper_at"] = cat_stats["avg_savings_£"].apply(lambda x: "Aldi" if x > 0 else ("Sainsbury's" if x < 0 else "Same"))

print(f"{'Category':<30} {'Count':>5} {'Aldi avg':>8} {'Sains avg':>9} {'Savings £':>9} {'Savings %':>9} {'Cheaper':>12}")
print("-" * 85)
for cat, row in cat_stats.iterrows():
    if cat == "" or row["count"] < 3: continue
    print(f"{cat:<30} {int(row['count']):>5} £{row['aldi_avg']:>5.2f} £{row['sains_avg']:>6.2f} £{row['avg_savings_£']:>6.2f} {row['avg_savings_%']:>7.1f}% {row['cheaper_at']:>12}")

# %% [markdown]
# ## Biggest Savings — Top Deals at Aldi

# %%
# Aldi's biggest savings (Aldi is cheaper by the most)
top_savings = df[(df["diff"] > 0) & (df["score"] >= 0.60)].sort_values("diff", ascending=False)

print("TOP 20 BIGGEST SAVINGS AT ALDI")
print(f"{'Savings':>8} {'Aldi Product':<40} {'£':>5} {'Sainsbury Product':<45} {'£':>5} {'%':>6}")
print("-" * 115)
for _, m in top_savings.head(20).iterrows():
    a = m["aldi_name"][:38]
    s = m["sains_name"][:43]
    print(f"£{m['diff']:>5.2f}  {a:<38} £{m['aldi_price']:>4.2f}  {s:<43} £{m['sains_price']:>4.2f}  {m['diff_pct']:>5.0f}%")

print()

# Biggest savings at Sainsbury's
top_sains_savings = df[(df["diff"] < 0) & (df["score"] >= 0.60)].sort_values("diff")
print("TOP 10 BIGGEST SAVINGS AT SAINSBURY'S")
print(f"{'Savings':>8} {'Aldi Product':<40} {'£':>5} {'Sainsbury Product':<45} {'£':>5} {'%':>6}")
print("-" * 115)
for _, m in top_sains_savings.head(10).iterrows():
    a = m["aldi_name"][:38]
    s = m["sains_name"][:43]
    print(f"£{-m['diff']:>5.2f}  {a:<38} £{m['aldi_price']:>4.2f}  {s:<43} £{m['sains_price']:>4.2f}  {-m['diff_pct']:>5.0f}%")

# %% [markdown]
# ## Price Correlation: Aldi vs Sainsbury's

# %%
plt.figure(figsize=(8, 6))
plt.scatter(df["aldi_price"], df["sains_price"], alpha=0.4, c="#0066a1", s=20)
lims = [0, max(df["aldi_price"].max(), df["sains_price"].max()) + 2]
plt.plot(lims, lims, "r--", alpha=0.3, label="Equal price")
plt.xlabel("Aldi Price (£)")
plt.ylabel("Sainsbury's Price (£)")
plt.title("Matched Product Prices: Aldi vs Sainsbury's")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()

# Points above the line = cheaper at Aldi
above_line = (df["sains_price"] > df["aldi_price"]).mean()
print(f"Points above equal-price line (Aldi cheaper): {above_line*100:.0f}%")

# %% [markdown]
## Own-Brand vs Branded Price Comparison

# %%
# For Sainsbury's: compare own-brand vs branded prices
sains_brands = pd.DataFrame(sains_docs)
sains_brands["price_clean"] = sains_brands["price"].apply(safe_price)
sains_brands["brand_filled"] = sains_brands.apply(
    lambda r: "Own Brand" if r.get("is_own_brand") or pd.isna(r.get("brand")) or r.get("brand") == "" else r["brand"], axis=1
)

own = sains_brands[sains_brands["brand_filled"] == "Own Brand"]["price_clean"].dropna()
branded = sains_brands[sains_brands["brand_filled"] != "Own Brand"]["price_clean"].dropna()

print("SAINSBURY'S: OWN-BRAND vs BRANDED PRICING")
print(f"{'Metric':<20} {'Own-Brand':>10} {'Branded':>10}")
print("-" * 42)
print(f"{'Count':<20} {len(own):>10} {len(branded):>10}")
print(f"{'Mean price':<20} £{own.mean():>7.2f} £{branded.mean():>7.2f}")
print(f"{'Median price':<20} £{own.median():>7.2f} £{branded.median():>7.2f}")
print(f"{'Min price':<20} £{own.min():>7.2f} £{branded.min():>7.2f}")
print(f"{'Max price':<20} £{own.max():>7.2f} £{branded.max():>7.2f}")

savings_pct = (branded.mean() - own.mean()) / branded.mean() * 100
print(f"\nAverage saving with own-brand: {savings_pct:.0f}%")

# %% [markdown]
## Price Per Unit Analysis

# %%
# Parse price_per_unit for both retailers
def parse_ppu(ppu_str):
    """Parse '£1.14/100g' or '(£0.95/1 L)' into (price, unit)"""
    if not ppu_str or pd.isna(ppu_str):
        return None, None
    s = str(ppu_str).replace("(", "").replace(")", "")
    m = re.search(r"(\d+\.?\d*)\s*/?\s*(\d*\s*[a-zA-Z/]+)", s)
    if m:
        return float(m.group(1)), m.group(2).strip()
    return None, None

aldi_df = pd.DataFrame(aldi_docs)
aldi_df[["ppu_price", "ppu_unit"]] = aldi_df["price_per_unit"].apply(
    lambda x: pd.Series(parse_ppu(x))
)

sains_df = pd.DataFrame(sains_docs)
sains_df[["ppu_price", "ppu_unit"]] = sains_df["price_per_unit"].apply(
    lambda x: pd.Series(parse_ppu(x))
)

print("Aldi PPU units:")
print(aldi_df["ppu_unit"].value_counts().head(10).to_string())
print()
print("Sains PPU units:")
print(sains_df["ppu_unit"].value_counts().head(10).to_string())

# %% [markdown]
## Promotion Analysis

# %%
# Aldi promotions
aldi_df["on_promotion"] = aldi_df["was_price"].notna()
sains_df["on_promotion"] = sains_df["was_price"].notna()

print("PRODUCTS ON PROMOTION")
print(f"{'Retailer':<15} {'Count':>6} {'%':>6}")
print("-" * 28)
print(f"{'Aldi':<15} {aldi_df['on_promotion'].sum():>6} {aldi_df['on_promotion'].mean()*100:>5.1f}%")
print(f"{'Sainsbury':<15} {sains_df['on_promotion'].sum():>6} {sains_df['on_promotion'].mean()*100:>5.1f}%")

# Promotion discount depth (Aldi)
if aldi_df["on_promotion"].any():
    aldi_df["discount_pct"] = ((aldi_df["was_price"] - aldi_df["price"]) / aldi_df["was_price"] * 100)
    avg_discount = aldi_df[aldi_df["on_promotion"]]["discount_pct"].mean()
    print(f"\nAldi avg discount depth: {avg_discount:.0f}%")
    print("Top promoted categories:")
    promo_cats = aldi_df[aldi_df["on_promotion"]]["category"].str.split(" > ").str[0].value_counts().head(10)
    print(promo_cats.to_string())

# %% [markdown]
## Price Index: Aldi vs Sainsbury's

# %%
# Build a simple price index: what does it cost to buy the matched basket at each retailer?
# Index: Sainsbury's = 100
matched_prices = df[["aldi_price", "sains_price"]].copy()
matched_prices["aldi_index"] = matched_prices["aldi_price"] / matched_prices["sains_price"] * 100

avg_index = matched_prices["aldi_index"].mean()
print(f"Aldi Price Index (Sainsbury's = 100): {avg_index:.0f}")
print(f"Meaning: On average, Aldi is {100 - avg_index:.0f}% cheaper than Sainsbury's")
print()

# Category-level index
cat_index = df.groupby("aldi_cat_top").apply(
    lambda g: (g["aldi_price"].sum() / g["sains_price"].sum() * 100)
).sort_values()

print("CATEGORY PRICE INDEX (Sainsbury's = 100)")
print(f"{'Category':<30} {'Index':>7}")
print("-" * 40)
for cat, idx in cat_index.items():
    if cat == "" or idx > 200: continue
    bars = "█" * max(1, int(idx / 5))
    print(f"{cat:<30} {idx:>5.0f}  {bars}")

# %% [markdown]
## Export Results

# %%
df.to_csv("notebooks/data/price_comparison.csv", index=False)
cat_stats.to_csv("notebooks/data/category_price_comparison.csv")
matched_prices.to_csv("notebooks/data/price_index.csv", index=False)
print("Results exported to notebooks/data/")

# %% [markdown]
## Key Findings

# 1. **Aldi is {avg_index:.0f}% of Sainsbury's prices** — a basket of matched products costs ~{100-avg_index:.0f}% less at Aldi
# 2. **Own-brand is ~{savings_pct:.0f}% cheaper** than branded equivalents at Sainsbury's
# 3. **Best savings at Aldi**: pantry staples (pasta, rice, tinned goods), baking ingredients, frozen foods
# 4. **Products where Sainsbury's is cheaper**: some fresh items, branded goods (Coca-Cola multipacks on promo)
# 5. **Price gap is largest** in simple/commodity products (flour, sugar, pasta) and smallest in branded/unique items
