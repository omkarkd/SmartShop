import os


MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "smartshop")

SECRET_KEY = os.getenv("SECRET_KEY", "smartshop-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

METRICS_ENABLED = os.getenv("METRICS_ENABLED", "true").lower() in ("true", "1", "yes")
