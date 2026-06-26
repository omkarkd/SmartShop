from fastapi import APIRouter, HTTPException, Header
from backend.models.user import UserSignup, UserLogin
from backend.services.auth_service import signup_user, login_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup")
def signup(body: UserSignup):
    result = signup_user(body.name, body.email, body.password)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/login")
def login(body: UserLogin):
    result = login_user(body.email, body.password, body.remember_me)
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])
    return result


@router.get("/me")
def me(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    from backend.services.auth_service import decode_token
    user = decode_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"user": user}
