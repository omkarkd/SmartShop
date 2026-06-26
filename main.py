from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.database import ensure_indexes
from backend.routers import auth, products, cart, normalized, brands, metrics, admin
from backend.metrics_middleware import PerformanceMetricsMiddleware
from backend.config import METRICS_ENABLED

app = FastAPI(title="SmartShop", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if METRICS_ENABLED:
    app.add_middleware(PerformanceMetricsMiddleware)
    app.include_router(metrics.router)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(normalized.router)
app.include_router(brands.router)
app.include_router(admin.router)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


@app.on_event("startup")
def startup():
    ensure_indexes()
