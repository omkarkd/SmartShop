from fastapi import APIRouter, HTTPException, Header
from backend.models.cart import CartItemAdd, CartItemUpdate
from backend.database import carts_collection, cart_items_collection
from backend.services.auth_service import decode_token
from backend.services.matching_service import find_matches
from bson import ObjectId
from datetime import datetime, timezone

router = APIRouter(prefix="/api/cart", tags=["cart"])


def get_user_id(authorization: str = Header(...)) -> str:
    token = authorization.replace("Bearer ", "")
    user = decode_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user["sub"]


@router.post("/create")
def create_cart(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    cart = {
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = carts_collection.insert_one(cart)
    return {"cart_id": str(result.inserted_id)}


@router.get("/active")
def get_active_cart(authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    cart = carts_collection.find_one({"user_id": user_id}, sort=[("created_at", -1)])
    if not cart:
        result = carts_collection.insert_one({
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })
        cart = carts_collection.find_one({"_id": result.inserted_id})

    items = list(cart_items_collection.find({"cart_id": str(cart["_id"])}))
    enriched = []
    for item in items:
        item["id"] = str(item["_id"])
        item.pop("_id", None)

        retailer = item.get("retailer")
        other_retailer = "sainsburys" if retailer == "aldi" else "aldi"
        matches = find_matches(item, retailer, min_score=0.3, limit=1)
        item["matched_item"] = matches[0] if matches else None

        enriched.append(item)

    aldi_total = sum(i["price"] * i.get("quantity", 1) for i in enriched if i["retailer"] == "aldi")
    sains_total = sum(i["price"] * i.get("quantity", 1) for i in enriched if i["retailer"] == "sainsburys")

    matched_aldi = 0
    matched_sains = 0
    for item in enriched:
        qty = item.get("quantity", 1)
        if item["retailer"] == "aldi":
            aldi_total += item["price"] * qty
            if item.get("matched_item"):
                matched_sains += item["matched_item"]["price"] * qty
            else:
                matched_sains += item["price"] * qty
        else:
            sains_total += item["price"] * qty
            if item.get("matched_item"):
                matched_aldi += item["matched_item"]["price"] * qty
            else:
                matched_aldi += item["price"] * qty

    return {
        "cart_id": str(cart["_id"]),
        "items": enriched,
        "totals": {
            "aldi_total": round(aldi_total, 2),
            "sainsburys_total": round(sains_total, 2),
            "matched_aldi_total": round(matched_aldi, 2),
            "matched_sainsburys_total": round(matched_sains, 2),
            "savings_aldi": round(matched_sains - aldi_total, 2) if aldi_total else 0,
            "savings_sainsburys": round(matched_aldi - sains_total, 2) if sains_total else 0,
        },
    }


@router.post("/add")
def add_item(body: CartItemAdd, authorization: str = Header(...)):
    user_id = get_user_id(authorization)
    cart = carts_collection.find_one({"user_id": user_id}, sort=[("created_at", -1)])
    if not cart:
        result = carts_collection.insert_one({
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })
        cart_id = str(result.inserted_id)
    else:
        cart_id = str(cart["_id"])

    item = {
        "cart_id": cart_id,
        "product_url": body.product_url,
        "retailer": body.retailer,
        "product_name": body.product_name,
        "price": body.price,
        "brand": body.brand,
        "size": body.size,
        "category": body.category,
        "image_url": body.image_url,
        "price_per_unit": body.price_per_unit,
        "is_own_brand": body.is_own_brand,
        "quantity": 1,
        "match_key": body.match_key,
        "added_at": datetime.now(timezone.utc),
    }

    existing = cart_items_collection.find_one({
        "cart_id": cart_id,
        "product_url": body.product_url,
    })
    if existing:
        cart_items_collection.update_one(
            {"_id": existing["_id"]},
            {"$inc": {"quantity": 1}}
        )
        return {"message": "Quantity increased", "item_id": str(existing["_id"])}

    result = cart_items_collection.insert_one(item)
    return {"message": "Item added", "item_id": str(result.inserted_id)}


@router.delete("/item/{item_id}")
def remove_item(item_id: str, authorization: str = Header(...)):
    get_user_id(authorization)
    result = cart_items_collection.delete_one({"_id": ObjectId(item_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Item removed"}


@router.put("/item/{item_id}")
def update_item(item_id: str, body: CartItemUpdate, authorization: str = Header(...)):
    get_user_id(authorization)
    result = cart_items_collection.update_one(
        {"_id": ObjectId(item_id)},
        {"$set": {"quantity": body.quantity}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Quantity updated"}
