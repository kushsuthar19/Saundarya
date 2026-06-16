"""
Security: JWT tokens, bcrypt hashing, role-based access control.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS)
bearer_scheme = HTTPBearer(auto_error=False)

ROLE_ADMIN = "admin"
ROLE_STAFF = "staff"

# Sections staff can access
STAFF_ALLOWED_SECTIONS = {"dash", "appt", "bridal", "daily", "clients"}
ADMIN_ONLY_SECTIONS = {"staff", "revenue", "reports"}


# ── Password ──────────────────────────────────────────────
def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────
def create_access_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, hashed_token)."""
    raw = secrets.token_urlsafe(64)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ── Current User ──────────────────────────────────────────
async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    token = None
    # Try Authorization header first
    if credentials:
        token = credentials.credentials
    # Fallback: HttpOnly cookie
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    return {
        "id": payload.get("sub"),
        "username": payload.get("username"),
        "role": payload.get("role"),
        "name": payload.get("name"),
    }


async def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


# ── Rate limit helper (in-memory, use Redis in prod) ──────
from collections import defaultdict
import time

_rate_store: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(key: str, max_calls: int, window_seconds: int = 60) -> bool:
    now = time.time()
    calls = _rate_store[key]
    # Remove old
    calls[:] = [t for t in calls if now - t < window_seconds]
    if len(calls) >= max_calls:
        return False
    calls.append(now)
    return True
