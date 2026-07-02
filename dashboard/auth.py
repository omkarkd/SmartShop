"""Authentication module for the Streamlit dashboard.

Uses a `users` collection in MongoDB for persistent auth with bcrypt
password hashing and role-based access control.
"""
import os
import bcrypt
from datetime import datetime, timezone, timedelta

from shared.db import get_db


# ── Role constants ──
ROLE_VIEWER = "viewer"
ROLE_ADMIN = "admin"

# Session expiry (default: 8 hours)
SESSION_TTL_HOURS = int(os.environ.get("SESSION_TTL_HOURS", "8"))


# ── User management ──

def seed_admin_user():
    """Create the initial admin user if no users exist in the database.

    Checks these env vars (in order):
      1. ADMIN_SEED_USER / ADMIN_SEED_PASS  (new, preferred)
      2. ADMIN_USER / ADMIN_PASS             (legacy fallback)
      3. Falls back to admin/admin with a warning (never block login)
    """
    db = get_db()
    if db["users"].count_documents({}) > 0:
        return  # already seeded

    seed_user = os.environ.get("ADMIN_SEED_USER") or os.environ.get("ADMIN_USER")
    seed_pass = os.environ.get("ADMIN_SEED_PASS") or os.environ.get("ADMIN_PASS")
    if not seed_user or not seed_pass:
        print("[auth] WARNING: No admin user configured. "
              "Set ADMIN_SEED_USER/ADMIN_SEED_PASS env vars. "
              "Falling back to admin/admin — CHANGE IMMEDIATELY.")
        seed_user = "admin"
        seed_pass = "admin"

    hashed = bcrypt.hashpw(seed_pass.encode("utf-8"), bcrypt.gensalt())
    db["users"].insert_one({
        "username": seed_user,
        "password_hash": hashed,
        "role": ROLE_ADMIN,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    print(f"[auth] Seeded admin user: {seed_user}")


def authenticate(username: str, password: str) -> dict | None:
    """Verify credentials against the users collection.

    Returns user dict (without password_hash) on success, None on failure.
    """
    db = get_db()
    user = db["users"].find_one({"username": username})
    if not user:
        return None
    if not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"]):
        return None
    # Return user without sensitive fields
    return {
        "username": user["username"],
        "role": user.get("role", ROLE_VIEWER),
        "created_at": user.get("created_at"),
    }


def create_user(username: str, password: str, role: str = ROLE_VIEWER) -> bool:
    """Create a new user. Only admin users can call this.

    Returns True on success, False if username already exists.
    """
    db = get_db()
    existing = db["users"].find_one({"username": username})
    if existing:
        return False
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    db["users"].insert_one({
        "username": username,
        "password_hash": hashed,
        "role": role,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return True


def check_role(username: str) -> str | None:
    """Get the role for a given username. Returns None if not found."""
    db = get_db()
    user = db["users"].find_one({"username": username}, {"role": 1})
    return user.get("role") if user else None


def is_session_expired(login_time: datetime | None) -> bool:
    """Check if a login session has expired."""
    if login_time is None:
        return True
    if isinstance(login_time, datetime) and login_time.tzinfo is None:
        login_time = login_time.replace(tzinfo=timezone.utc)
    elapsed = datetime.now(timezone.utc) - login_time
    return elapsed > timedelta(hours=SESSION_TTL_HOURS)
