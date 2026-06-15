from fastapi import APIRouter, Query
from backend.services.brand_service import extract_brand
from backend.database import aldi_products, sainsburys_products
from pymongo import MongoClient
from backend.config import MONGO_URI, DB_NAME

router = APIRouter(prefix="/api/brands", tags=["brands"])

client = MongoClient(MONGO_URI)
db = client[DB_NAME]


@router.get("/extract")
def extract(q: str = Query(..., min_length=1)):
    brand, confidence, method = extract_brand(q)
    return {
        "product_name": q,
        "extracted_brand": brand,
        "confidence": confidence,
        "method": method,
    }


@router.post("/extract")
def extract_batch(names: list[str]):
    results = []
    for name in names:
        brand, confidence, method = extract_brand(name)
        results.append({
            "product_name": name,
            "extracted_brand": brand,
            "confidence": confidence,
            "method": method,
        })
    return {"results": results}


@router.get("/list")
def list_brands(retailer: str = None):
    if retailer:
        coll = aldi_products if retailer == "aldi" else sainsburys_products
        brands = coll.distinct("brand")
    else:
        brands = db["branded_products"].distinct("final_brand")
    brands = [b for b in brands if b and b.strip()]
    return {"brands": sorted(set(brands))}
