from fastapi import APIRouter, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from backend.services.admin_service import (
    verify_admin,
    create_admin_token,
    verify_admin_token,
    get_dashboard_overview,
    get_scraping_runs,
    get_scraping_run_detail,
    get_database_dashboard,
    get_service_health,
)
from typing import Optional

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(authorization: Optional[str] = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    token = authorization.replace("Bearer ", "")
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return token


@router.post("/login")
def admin_login(body: dict):
    username = body.get("username", "")
    password = body.get("password", "")
    if not verify_admin(username, password):
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    token = create_admin_token()
    return {"token": token, "role": "admin"}


@router.get("/dashboard")
def admin_dashboard(authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    return JSONResponse(get_dashboard_overview())


@router.get("/scraping-runs")
def admin_scraping_runs(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    retailer: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    authorization: Optional[str] = Header(None),
):
    _require_admin(authorization)
    return JSONResponse(get_scraping_runs(date_from, date_to, retailer, status, page, per_page))


@router.get("/scraping-runs/{run_id}")
def admin_scraping_run_detail(run_id: str, authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    return JSONResponse(get_scraping_run_detail(run_id))


@router.get("/database")
def admin_database(authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    return JSONResponse(get_database_dashboard())


@router.get("/health")
def admin_health(authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    return JSONResponse(get_service_health())
