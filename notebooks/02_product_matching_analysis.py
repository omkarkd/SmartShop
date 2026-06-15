# %% [markdown]
# # 02 — Product Matching Analysis
# 
# Test and refine the cross-retailer product matching algorithm. Find which products exist at both Aldi and Sainsbury's,
# evaluate match quality, and visualise the results.

# %% [markdown]
# ## Setup & Imports

# %%
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import json
from collections import defaultdict
from difflib import SequenceMatcher

from collections import Counter
import pymongo
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

try:
    from IPython.display import display
except ImportError:
    def display(x):
        if hasattr(x, 'to_string'):
            print(x.to_string())
        else:
            print(x)

# %% [markdown]
# ## Connect & Load Data

# %%
client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["smartshop"]

aldi_docs = list(db["aldi_products"].find({}, {"_id": 0}))
sains_docs = list(db["sainsburys_products"].find({}, {"_id": 0}))

# Also load the matching service
from backend.services.matching_service import find_matches, score_match, normalize_name

print(f"Aldi: {len(aldi_docs)} products")
print(f"Sainsbury's: {len(sains_docs)} products")

# %% [markdown]
# ## Test Specific Product Matches
# Let's test the matching for common grocery items.

# %%
def show_matches(product, retailer):
    """Pretty-print matches for a product"""
    matches = find_matches(product, retailer, min_score=0.2, limit=5)
    name = product.get("product_name", "?")
    price = product.get("price", 0)
    print(f"{'='*70}")
    print(f"  [{retailer}] {name}  —  £{float(price):.2f}")
    print(f"{'='*70}")
    if not matches:
        print("  → No matches found")
    for i, m in enumerate(matches, 1):
        other = "Sainsbury's" if retailer == "aldi" else "Aldi"
        mp = float(m.get("price", 0)) if m.get("price") else 0
        diff = mp - float(price)
        arrow = "🔻 cheaper" if diff < 0 else ("🔺 costlier" if diff > 0 else "  same")
        print(f"  {i}. [{other}] {m['product_name'][:50]:50s} £{mp:>5.2f}  ({arrow})  score={m.get('match_score', 0):.2f}")
    print()

# Test products
test_products = [
    ("Bananas", "aldi"),
    ("British Semi Skimmed Milk 1.7% Fat", "aldi"),
    ("Free Range Eggs 6 Pack", "aldi"),
    ("Strawberries", "aldi"),
    ("Jazz Apples", "aldi"),
    ("Wholemeal Bread", "aldi"),
    ("Unsmoked Back Bacon 10 Rashers", "aldi"),
    ("Coca-Cola Zero Sugar", "aldi"),
]

for name, retailer in test_products:
    prod = db[f"{retailer}_products"].find_one({"product_name": {"$regex": name, "$options": "i"}})
    if prod:
        show_matches(prod, retailer)

# %% [markdown]
# ## Batch Matching: Find All Cross-Retailer Matches

# %%
def safe_price(val):
    if val is None: return None
    try: return float(val)
    except: return None

# Use a subset for performance in this analysis
ALDI_SAMPLE_SIZE = 1000
SAINS_SAMPLE_SIZE = 1000

import random
random.seed(42)
aldi_sample = random.sample(aldi_docs, min(ALDI_SAMPLE_SIZE, len(aldi_docs)))
sains_sample = random.sample(sains_docs, min(SAINS_SAMPLE_SIZE, len(sains_docs)))

print(f"\nUsing {len(aldi_sample)} Aldi and {len(sains_sample)} Sainsbury's products for matching...\n")

# Match Aldi → Sainsbury's
matches_aldi_to_sains = []
for i, p in enumerate(aldi_sample):
    if i % 200 == 0 and i > 0:
        print(f"  Progress: {i}/{len(aldi_sample)}")
    ms = find_matches(p, "aldi", min_score=0.45, limit=1)
    if not ms:
        continue
    m = ms[0]
    ap = safe_price(p.get("price"))
    sp = safe_price(m.get("price"))
    if ap is None or sp is None:
        continue
    matches_aldi_to_sains.append({
        "aldi_name": p["product_name"],
        "aldi_price": ap,
        "aldi_category": p.get("category", ""),
        "aldi_brand": p.get("brand", ""),
        "sains_name": m["product_name"],
        "sains_price": sp,
        "sains_category": m.get("category", ""),
        "sains_brand": m.get("brand", ""),
        "score": m.get("match_score", 0),
        "diff": round(sp - ap, 2),
        "diff_pct": round((sp - ap) / ap * 100, 1) if ap > 0 else 0,
    })

# Match Sainsbury's → Aldi (reverse direction)
matches_sains_to_aldi = []
for i, p in enumerate(sains_sample):
    if i % 200 == 0 and i > 0:
        print(f"  Progress: {i}/{len(sains_sample)}")
    ms = find_matches(p, "sainsburys", min_score=0.45, limit=1)
    if not ms:
        continue
    m = ms[0]
    ap = safe_price(m.get("price"))
    sp = safe_price(p.get("price"))
    if ap is None or sp is None:
        continue
    matches_sains_to_aldi.append({
        "sains_name": p["product_name"],
        "sains_price": sp,
        "sains_category": p.get("category", ""),
        "sains_brand": p.get("brand", ""),
        "aldi_name": m["product_name"],
        "aldi_price": ap,
        "aldi_category": m.get("category", ""),
        "aldi_brand": m.get("brand", ""),
        "score": m.get("match_score", 0),
        "diff": round(sp - ap, 2),
        "diff_pct": round((sp - ap) / ap * 100, 1) if ap > 0 else 0,
    })

df_a2s = pd.DataFrame(matches_aldi_to_sains)
df_s2a = pd.DataFrame(matches_sains_to_aldi)

print(f"Aldi → Sainsbury's matches: {len(df_a2s)} ({len(df_a2s)/len(aldi_docs)*100:.0f}% of Aldi products)")
print(f"Sainsbury's → Aldi matches: {len(df_s2a)} ({len(df_s2a)/len(sains_docs)*100:.0f}% of Sainsbury's products)")

# %% [markdown]
# ## Match Quality Distribution

# %%
fig, axes = plt.subplots(1, 2, figsize=(12, 4))

axes[0].hist(df_a2s["score"], bins=20, color="#0066a1", alpha=0.7, edgecolor="white")
axes[0].axvline(x=0.6, color="orange", linestyle="--", label="threshold=0.6")
axes[0].set_xlabel("Match Score")
axes[0].set_ylabel("Count")
axes[0].set_title("Match Score Distribution (Aldi → Sains)")
axes[0].legend()

axes[1].hist(df_s2a["score"], bins=20, color="#e87722", alpha=0.7, edgecolor="white")
axes[1].axvline(x=0.6, color="orange", linestyle="--", label="threshold=0.6")
axes[1].set_xlabel("Match Score")
axes[1].set_ylabel("Count")
axes[1].set_title("Match Score Distribution (Sains → Aldi)")
axes[1].legend()

plt.tight_layout()
plt.show()

# High-confidence matches (score >= 0.65)
high_conf = df_a2s[df_a2s["score"] >= 0.65]
print(f"High-confidence matches (score ≥ 0.65): {len(high_conf)}")

# %% [markdown]
# ## Best & Worst Matches

# %%
# Top 20 best matches
print("TOP 20 BEST MATCHES (Aldi → Sainsbury's)")
print(f"{'Score':>5} {'Aldi':<40} {'£':>5} {'Sainsbury':<45} {'£':>5} {'Diff':>6}")
print("-" * 110)
for _, m in df_a2s.sort_values("score", ascending=False).head(20).iterrows():
    a = m["aldi_name"][:38]
    s = m["sains_name"][:43]
    sav = "Aldi +{:.2f}".format(m["diff"]) if m["diff"] > 0 else ("Sains {:.2f}".format(-m["diff"]) if m["diff"] < 0 else "same")
    print(f"{m['score']:>5.2f}  {a:<38} £{m['aldi_price']:>4.2f}  {s:<43} £{m['sains_price']:>4.2f}  {sav:>10}")

print()

# Bottom 20 worst (lowest score matches)
print("BOTTOM 20 MATCHES (worst quality)")
for _, m in df_a2s.sort_values("score").head(20).iterrows():
    print(f"{m['score']:>5.2f}  [{m['aldi_name'][:35]:35s}] → [{m['sains_name'][:45]:45s}]  £{m['aldi_price']:.2f}→£{m['sains_price']:.2f}")

# %% [markdown]
# ## False Positive Analysis

# %%
# Find likely false positives (same word matched but different products)
# e.g., "Wholemeal Baps" → "Wholemeal Pittas" — baps ≠ pittas
# e.g., "Protein Pancakes" → "Protein Yogurt" — pancakes ≠ yogurt

def is_false_positive(row):
    """Heuristic: if first 3 chars of last word differ, might be wrong"""
    a_words = normalize_name(row["aldi_name"]).split()
    s_words = normalize_name(row["sains_name"]).split()
    if not a_words or not s_words:
        return False
    a_last = a_words[-1][:4]
    s_last = s_words[-1][:4]
    return a_last != s_last and len(a_words) > 1 and len(s_words) > 1

# %%
df_a2s["suspicious"] = df_a2s.apply(is_false_positive, axis=1)
false_positives = df_a2s[df_a2s["suspicious"] & (df_a2s["score"] < 0.60)]
print(f"Suspected false positives: {len(false_positives)}")
display(false_positives[["score", "aldi_name", "sains_name", "aldi_category", "sains_category"]].head(20))

# %% [markdown]
# ## Price Difference Distribution

# %%
fig, axes = plt.subplots(1, 2, figsize=(14, 4))

# Price difference histogram (limited to sensible range)
diff_limited = df_a2s[(df_a2s["diff"] > -10) & (df_a2s["diff"] < 20)]
axes[0].hist(diff_limited["diff"], bins=40, color="#0066a1", alpha=0.7, edgecolor="white")
axes[0].axvline(x=0, color="red", linestyle="--")
axes[0].set_xlabel("Price Difference (£)  —  positive = Aldi cheaper")
axes[0].set_ylabel("Count")
axes[0].set_title("Price Difference Distribution (Aldi price − Sains price)")

# Percentage savings
pct_limited = df_a2s[(df_a2s["diff_pct"] > -50) & (df_a2s["diff_pct"] < 500)& (df_a2s["score"] >= 0.55)]
axes[1].hist(pct_limited["diff_pct"], bins=40, color="#e87722", alpha=0.7, edgecolor="white")
axes[1].axvline(x=0, color="red", linestyle="--")
axes[1].set_xlabel("Savings % at Aldi")
axes[1].set_ylabel("Count")
axes[1].set_title("Percentage Savings at Aldi (matched products only)")

plt.tight_layout()
plt.show()

# Stats
high_quality = df_a2s[(df_a2s["score"] >= 0.60) & (df_a2s["aldi_price"] < 30) & (df_a2s["sains_price"] < 30)]
print(f"High-quality, sensible-priced matches: {len(high_quality)}")
print(f"Aldi cheaper:  {len(high_quality[high_quality['diff'] > 0])} ({(high_quality['diff'] > 0).mean()*100:.0f}%)")
print(f"Sains cheaper: {len(high_quality[high_quality['diff'] < 0])} ({(high_quality['diff'] < 0).mean()*100:.0f}%)")
print(f"Same price:    {len(high_quality[high_quality['diff'] == 0])}")
print(f"Avg diff:      £{high_quality['diff'].mean():.2f}")
print(f"Avg savings %: {high_quality['diff_pct'].mean():.0f}%")

# %% [markdown]
# ## Category-Level Match Analysis

# %%
# Which categories have the most matches?
cat_match_counts = df_a2s["aldi_category"].str.split(" > ").str[0].value_counts()
cat_total = pd.Series({c.split(" > ")[0]: n for c, n in Counter(d["category"] for d in aldi_docs).items()})

cat_stats = pd.DataFrame({
    "total": cat_total,
    "matched": cat_match_counts,
}).fillna(0).astype(int)
cat_stats["match_rate"] = (cat_stats["matched"] / cat_stats["total"] * 100).round(1)
cat_stats = cat_stats[cat_stats["total"] >= 10].sort_values("match_rate", ascending=False)

print("Category Match Rates (Aldi → Sainsbury's)")
print(f"{'Category':<25} {'Total':>6} {'Matched':>8} {'Rate':>6}")
print("-" * 48)
for cat, row in cat_stats.iterrows():
    if cat == "": continue
    print(f"{cat:<25} {int(row['total']):>6} {int(row['matched']):>8} {row['match_rate']:>5.1f}%")

# %% [markdown]
# ## Improving the Matcher
# 
# Testing alternative scoring approaches:

# %%
def improved_score(p1, p2):
    """Alternative scoring: Jaccard word overlap + brand bonus + category bonus"""
    n1 = normalize_name(p1.get("product_name", ""))
    n2 = normalize_name(p2.get("product_name", ""))
    if not n1 or not n2:
        return 0

    w1 = set(w for w in n1.split() if len(w) > 2)
    w2 = set(w for w in n2.split() if len(w) > 2)
    if not w1 or not w2:
        return 0

    # Jaccard similarity on important words
    jaccard = len(w1 & w2) / len(w1 | w2)

    # Sequence matcher on the full name
    seq = SequenceMatcher(None, n1, n2).ratio()

    # Combined score
    name_score = max(jaccard, seq * 0.5 + jaccard * 0.5)

    # Brand bonus
    b1 = (p1.get("brand") or "").lower().strip()
    b2 = (p2.get("brand") or "").lower().strip()
    brand_bonus = 0.15 if b1 and b2 and (b1 == b2 or b1 in b2 or b2 in b1) else 0

    # Category bonus (subcategory match)
    c1 = (p1.get("category", "") or "").split(" > ")[-1].strip().lower()[:10]
    c2 = (p2.get("category", "") or "").split(" > ")[-1].strip().lower()[:10]
    cat_bonus = 0.1 if c1 and c2 and c1 == c2 else 0

    # Size match bonus
    sz1 = re.search(r"(\d+)\s*(g|kg|ml|l|cl)", n1)
    sz2 = re.search(r"(\d+)\s*(g|kg|ml|l|cl)", n2)
    size_bonus = 0.08 if sz1 and sz2 and sz1.group() == sz2.group() else 0

    return name_score + brand_bonus + cat_bonus + size_bonus

# %%
# Compare old vs new scoring
test_prod = aldi_docs[0]
test_sains = sains_docs[0]

print(f"Old score: {score_match(test_prod, test_sains):.3f}")
print(f"New score: {improved_score(test_prod, test_sains):.3f}")

# Test on a sample
scores_old = []
scores_new = []
sample = list(zip(matches_aldi_to_sains[:100], df_a2s.head(100).to_dict("records")))
for i, (match_info, row) in enumerate(zip(matches_aldi_to_sains[:100], df_a2s.head(100).to_dict("records"))):
    ap = aldi_docs[i]
    sp = next((d for d in sains_docs if d.get("product_name") == row["sains_name"]), None)
    if ap and sp:
        scores_old.append(score_match(ap, sp))
        scores_new.append(improved_score(ap, sp))

print(f"\nOld scoring avg: {np.mean(scores_old):.3f}")
print(f"New scoring avg: {np.mean(scores_new):.3f}")
print(f"Improvement:     {((np.mean(scores_new) - np.mean(scores_old)) / np.mean(scores_old) * 100):.0f}%")

# %% [markdown]
# ## Export Match Results

# %%
# Save to CSV for dashboard/analysis
df_a2s.to_csv("notebooks/data/matches_aldi_to_sains.csv", index=False)
df_s2a.to_csv("notebooks/data/matches_sains_to_aldi.csv", index=False)
print(f"Saved {len(df_a2s)} + {len(df_s2a)} matches to notebooks/data/")

# %% [markdown]
# ## Summary
# 
# - **Matching coverage**: {len(df_a2s)}/{len(aldi_docs)} ({len(df_a2s)/len(aldi_docs)*100:.0f}%) Aldi products matched to Sainsbury's
# - **High-confidence (≥0.65)**: {len(df_a2s[df_a2s['score'] >= 0.65])} matches
# - **Aldi cheaper in**: {(df_a2s['diff'] > 0).mean()*100:.0f}% of matched cases
# - **Average savings**: £{df_a2s['diff'].mean():.2f} per product at Aldi
# - **Problem areas**: Short product names (e.g. "Bananas") cause broad matches; different product types with similar names (e.g. "baps" vs "pittas") create false positives
