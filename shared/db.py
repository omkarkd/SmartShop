from datetime import datetime, timezone
from pymongo import MongoClient
from shared.config import load

_client = None


def get_db():
    global _client
    uri, db_name = load()
    if _client is None:
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    return _client[db_name]


def close():
    global _client
    if _client:
        _client.close()
        _client = None


def ensure_aware(dt):
    """Convert a naive datetime to timezone-aware (UTC) if needed."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
