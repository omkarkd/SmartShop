# %% [markdown]
# # 05 — Milk & Cheese Product Name Normalization
# 
# Transform raw product names from Aldi and Sainsbury's into structured data:
# **Brand** | **Product Name** | **Size** | **Price** | **Attributes**
# 
# Only targets **Milk** and **Cheese** categories. Original data is NOT modified.

# %% [markdown]
# ## Setup

# %%
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import pymongo
import pandas as pd

from notebooks.product_normalizer import (
    normalize_milk_cheese_product,
    get_milk_cheese_products,
    find_by_product_name,
)

client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["smartshop"]

# %% [markdown]
# ## Load & Normalize Milk + Cheese

# %%
print("Loading products from Milk and Cheese categories...")

aldi_normalized = get_milk_cheese_products(db, "aldi")
sains_normalized = get_milk_cheese_products(db, "sainsburys")

print(f"Aldi milk/cheese:        {len(aldi_normalized)}")
print(f"Sainsbury's milk/cheese: {len(sains_normalized)}")

# %% [markdown]
# ## Before & After: Milk Samples

# %%
# Aldi milk samples
print("=== ALDI MILK: Original → Normalized ===\n")
aldi_milk = [p for p in aldi_normalized if "milk" in p["product_name"].lower()]
for p in aldi_milk[:12]:
    print(f"  Original:    {p['original_name']}")
    print(f"  Normalized:  {p['product_name']}")
    print(f"  Brand:       {p['brand']}")
    print(f"  Size:        {p['size']}")
    print(f"  Price:       £{p['price']:.2f}")
    print(f"  Attributes:  {', '.join(p['attributes']) if p['attributes'] else '(none)'}")
    print()

# %% [markdown]
# ## Before & After: Sainsbury's Milk

# %%
print("=== SAINSBURY'S MILK: Original → Normalized ===\n")
sains_milk = [p for p in sains_normalized if "milk" in p["product_name"].lower()]
for p in sains_milk[:15]:
    print(f"  Original:    {p['original_name']}")
    print(f"  Normalized:  {p['product_name']}")
    print(f"  Brand:       {p['brand']}")
    print(f"  Size:        {p['size']}")
    print(f"  Price:       £{p['price']:.2f}")
    print(f"  Attributes:  {', '.join(p['attributes']) if p['attributes'] else '(none)'}")
    print()

# %% [markdown]
# ## Before & After: Cheese

# %%
print("=== ALDI CHEESE: Original → Normalized ===\n")
aldi_cheese = [p for p in aldi_normalized if "cheese" in p["category"].lower()]
for p in aldi_cheese[:12]:
    print(f"  Original:    {p['original_name']}")
    print(f"  Normalized:  {p['product_name']}")
    print(f"  Brand:       {p['brand']}")
    print(f"  Size:        {p['size']}")
    print(f"  Price:       £{p['price']:.2f}")
    print()

# %%
print("=== SAINSBURY'S CHEESE: Original → Normalized ===\n")
sains_cheese = [p for p in sains_normalized if "cheese" in p["category"].lower()]
for p in sains_cheese[:12]:
    print(f"  Original:    {p['original_name']}")
    print(f"  Normalized:  {p['product_name']}")
    print(f"  Brand:       {p['brand']}")
    print(f"  Size:        {p['size']}")
    print(f"  Price:       £{p['price']:.2f}")
    print()

# %% [markdown]
# ## Search: Find "Whole Milk" across both retailers

# %%
all_normalized = aldi_normalized + sains_normalized

for query in ["whole milk", "semi skimmed milk", "cheddar cheese", "mozzarella"]:
    results = find_by_product_name(all_normalized, query)
    print(f"\n{'='*60}")
    print(f"  Search: \"{query}\" — {len(results)} results")
    print(f"{'='*60}")
    for p in results:
        attr = f" [{', '.join(p['attributes'])}]" if p['attributes'] else ""
        print(f"  [{p['retailer']:>10}] {p['brand']:15s} | {p['product_name']:25s} | {p['size'] or '?':10s} | £{p['price']:.2f}{attr}")

# %% [markdown]
# ## Comparison Table: Aldi vs Sainsbury's Milk

# %%
print("=== MILK PRICE COMPARISON (Normalized Names) ===\n")
print(f"{'Product':<30} {'Aldi Brand':<14} {'Size':<12} {'Aldi £':>7} {'Sains Brand':<16} {'Size':<12} {'Sains £':>7}")
print("-" * 105)

# Group by normalized product name
from collections import defaultdict
by_product = defaultdict(lambda: {"aldi": [], "sainsburys": []})

for p in all_normalized:
    key = p["product_name"] + "|" + "|".join(sorted(p["attributes"]))
    by_product[key][p["retailer"]].append(p)

for key in sorted(by_product.keys()):
    aldi_items = by_product[key]["aldi"]
    sains_items = by_product[key]["sainsburys"]
    if not aldi_items or not sains_items:
        continue
    # Show first match from each
    a = aldi_items[0]
    s = sains_items[0]
    print(f"{a['product_name']:<30} {a['brand']:<14} {a['size'] or '?':<12} £{a['price']:>5.2f} {s['brand']:<16} {s['size'] or '?':<12} £{s['price']:>5.2f}")

# %% [markdown]
# ## Export Normalized Data

# %%
df_aldi = pd.DataFrame(aldi_normalized)
df_sains = pd.DataFrame(sains_normalized)
df_all = pd.concat([df_aldi, df_sains], ignore_index=True)

df_all.to_csv("notebooks/data/milk_cheese_normalized.csv", index=False)
print(f"Exported {len(df_all)} normalized products to notebooks/data/milk_cheese_normalized.csv")

# Summary statistics
print("\n=== SUMMARY ===")
print(f"{'Retailer':<15} {'Category':<15} {'Count':>6}")
print("-" * 38)
for retailer, group in df_all.groupby("retailer"):
    for cat, sub in group.groupby(df_all["original_name"].str.contains("(?i)cheese").map({True: "Cheese", False: "Milk"})):
        print(f"{retailer:<15} {cat:<15} {len(sub):>6}")

# %% [markdown]
# ## How It Works
# 
# The `product_normalizer.py` module applies these steps to each product name:
# 
# 1. **Remove fat %** — strips "1.7% Fat", "<0.5% Fat" etc.
# 2. **Extract size** — detects patterns like "2.27L", "568ml", "2 pint", "400g"
# 3. **Extract brand** — checks known brand prefixes (Sainsbury's, Arla, Cravendale, Cowbelle, etc.)
# 4. **Extract product type** — matches against known milk/cheese type patterns
# 5. **Extract attributes** — remaining descriptive words (Organic, Filtered, British, etc.)
# 
# **Key design decisions:**
# - Aldi brand comes from the `brand` field (always populated)
# - Sainsbury's brand is extracted from the product name prefix
# - Product type matching uses longest-first to avoid partial matches
# - Original data is NEVER modified — this is a pure transformation layer
