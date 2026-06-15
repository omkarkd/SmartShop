from fastapi import APIRouter, Query
from backend.services.product_service import search_products, get_categories, get_products_by_category, get_product_by_url
from typing import Optional

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("/search")
def search(
    q: str = Query(..., min_length=1),
    retailer: Optional[str] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
):
    results = search_products(q, retailer, category, brand, page, per_page)
    return {"products": results, "total": len(results)}


@router.get("/categories")
def categories(retailer: Optional[str] = None):
    cats = get_categories(retailer)
    return {"categories": [{"name": c[0], "retailer": c[1]} for c in cats]}


@router.get("/category/{category_name}")
def by_category(
    category_name: str,
    retailer: Optional[str] = None,
    brand: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
):
    results = get_products_by_category(category_name, retailer, brand, page, per_page)
    return {"products": results, "total": len(results)}


@router.get("/{url:path}")
def by_url(url: str):
    product = get_product_by_url(url)
    if not product:
        return {"product": None}
    return {"product": product}
