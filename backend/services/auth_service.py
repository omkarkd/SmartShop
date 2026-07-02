from datetime import datetime, timedelta, timezone
from bson import ObjectId
import bcrypt
from jose import JWTError, jwt
from backend.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from backend.database import users_collection


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict, expires_minutes: int = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def signup_user(name: str, email: str, password: str) -> dict:
    if users_collection.find_one({"email": email}):
        return {"error": "Email already registered"}
    user = {
        "name": name,
        "email": email,
        "password": hash_password(password),
        "created_at": datetime.now(timezone.utc),
    }
    result = users_collection.insert_one(user)
    token = create_access_token({"sub": str(result.inserted_id), "email": email})
    return {"token": token, "user": {"id": str(result.inserted_id), "name": name, "email": email}}


def login_user(email: str, password: str, remember_me: bool = False) -> dict:
    user = users_collection.find_one({"email": email})
    if not user or not verify_password(password, user["password"]):
        return {"error": "Invalid email or password"}
    expires_in = 60 * 24 if remember_me else 5
    token = create_access_token({"sub": str(user["_id"]), "email": email}, expires_in)
    return {
        "token": token,
        "user": {"id": str(user["_id"]), "name": user["name"], "email": user["email"]},
        "remember_me": remember_me,
        "expires_in": expires_in,
    }


def get_current_user(token: str) -> dict:
    payload = decode_token(token)
    if payload is None:
        return None
    user = users_collection.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        return None
    return {"id": str(user["_id"]), "name": user["name"], "email": user["email"]}
