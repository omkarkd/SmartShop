from pydantic import BaseModel
from typing import Optional


class CartItemAdd(BaseModel):
    product_url: str
    retailer: str
    product_name: str
    price: float
    brand: Optional[str] = None
    size: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    price_per_unit: Optional[str] = None
    is_own_brand: Optional[bool] = None
    match_key: Optional[str] = None


class CartItemUpdate(BaseModel):
    quantity: int
