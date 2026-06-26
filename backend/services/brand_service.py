import csv, re, os
from difflib import SequenceMatcher

_KB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "notebook", "llm_master_brand.csv")

_registry = None


def _load_registry():
    global _registry
    if _registry is not None:
        return _registry
    kb = {}
    with open(_KB_PATH) as f:
        for row in csv.DictReader(f):
            n = row["names"].strip()
            b = row["Brand"].strip()
            if b and b != "Unknown" and len(b) >= 3:
                kb[n.lower()] = b
    registry = {}
    for pn, b in kb.items():
        bl = b.lower()
        if bl not in registry:
            registry[bl] = {"brand": b, "variants": set()}
        registry[bl]["variants"].add(pn.split()[0].lower().strip("'\""))
    registry = {k: v for k, v in registry.items() if len(k) >= 3}
    _registry = registry
    return registry


def _norm(t):
    return re.sub(r"\s+", " ", t.lower()).strip()


def extract_brand(text):
    reg = _load_registry()
    n = _norm(text)

    # Prefix
    bb, bs = None, 0.0
    for bl, info in reg.items():
        if n.startswith(bl):
            s = min(1.0, 0.7 + len(bl) / 50)
            if s > bs: bs, bb = s, info["brand"]
        for v in info["variants"]:
            if n.startswith(v):
                s = 0.5 + len(v) / 30
                if s > bs: bs, bb = s, info["brand"]
    if bb and bs >= 0.7:
        return bb, round(bs, 2), "prefix"

    # Anywhere
    bb, bs = None, 0.0
    for bl, info in reg.items():
        if bl in n:
            bonus = 0.1 if n.startswith(bl) else 0
            s = 0.6 + bonus + len(bl) / 60
            if s > bs: bs, bb = s, info["brand"]
    if bb and bs >= 0.6:
        return bb, round(bs, 2), "anywhere"

    # Fuzzy
    bb, bs = None, 0.0
    words = n.split()
    for ng in range(1, min(5, len(words) + 1)):
        for i in range(len(words) - ng + 1):
            ngram = " ".join(words[i:i + ng])
            for bl, info in reg.items():
                sim = SequenceMatcher(None, ngram, bl).ratio()
                if sim >= 0.75 and sim > bs:
                    bs, bb = sim, info["brand"]
    if bb and bs >= 0.75:
        return bb, round(bs, 2), "fuzzy"

    return None, 0.0, "none"
