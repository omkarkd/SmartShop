from pydantic import BaseModel
from typing import Optional


class ProductResponse(BaseModel):
    url: Optional[str] = None
    product_name: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[float] = None
    was_price: Optional[float] = None
    price_with_promotion: Optional[float] = None
    price_per_unit: Optional[str] = None
    image_url: Optional[str] = None
    is_own_brand: Optional[bool] = None
    size: Optional[str] = None
    promotion_badge: Optional[str] = None
    retailer: Optional[str] = None
