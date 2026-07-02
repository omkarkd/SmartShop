from fastapi import APIRouter, Query
from backend.database import db
from backend.services.normalizer_service import normalize_product

router = APIRouter(prefix="/api/normalized", tags=["normalized"])


@router.get("/search")
def search_normalized(q: str = Query(..., min_length=1), retailer: str = None):
    regex_query = {"$regex": q, "$options": "i"}
    and_filters = [{"product_name": regex_query}]

    results = []
    for r in ["aldi", "sainsburys"]:
        if retailer and r != retailer:
            continue
        col = db[f"{r}_products"]
        for doc in col.find({"$and": and_filters}).limit(50):
            normalized = normalize_product(doc, r)
            results.append(normalized)

    return {"products": results, "total": len(results)}
