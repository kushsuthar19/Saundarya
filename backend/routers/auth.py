"""
Authentication endpoints.
"""
import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
import oracledb

from backend.core.database import get_db
from backend.core.security import (
    verify_password, create_access_token, create_refresh_token,
    get_current_user, check_rate_limit, hash_password
)
from backend.core.config import settings
from backend.schemas.schemas import LoginRequest, TokenResponse, RefreshRequest, ChangePasswordRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: oracledb.AsyncConnection = Depends(get_db),
):
    ip = request.client.host if request.client else "unknown"

    # Rate limit by IP
    if not check_rate_limit(f"login:{ip}", settings.RATE_LIMIT_LOGIN, 60):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again in 1 minute.")

    # Fetch user
    cursor = db.cursor()
    await cursor.execute(
        """SELECT id, username, full_name, hashed_pw, role, is_active,
                  failed_logins, locked_until
           FROM users WHERE username = :1""",
        [req.username]
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id, username, full_name, hashed_pw, role, is_active, failed_logins, locked_until = row

    # Check active
    if not is_active:
        raise HTTPException(status_code=401, detail="Account deactivated")

    # Check lockout
    if locked_until and datetime.now(timezone.utc) < locked_until.replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=429, detail=f"Account locked. Try again later.")

    # Verify password
    if not verify_password(req.password, hashed_pw):
        new_fails = (failed_logins or 0) + 1
        lock_sql = ""
        if new_fails >= settings.MAX_LOGIN_ATTEMPTS:
            lock_until = datetime.now(timezone.utc) + timedelta(minutes=settings.LOCKOUT_MINUTES)
            lock_sql = f", locked_until = TO_TIMESTAMP('{lock_until.strftime('%Y-%m-%d %H:%M:%S')}', 'YYYY-MM-DD HH24:MI:SS')"

        await cursor.execute(
            f"UPDATE users SET failed_logins = :1 {lock_sql} WHERE id = :2",
            [new_fails, user_id]
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Reset failed logins
    await cursor.execute(
        "UPDATE users SET failed_logins = 0, locked_until = NULL, last_login = SYSTIMESTAMP WHERE id = :1",
        [user_id]
    )

    # Create tokens
    token_data = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "name": full_name,
    }
    access_token = create_access_token(token_data)
    raw_refresh, hashed_refresh = create_refresh_token()
    refresh_expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    # Store refresh token
    ua = request.headers.get("user-agent", "")[:256]
    await cursor.execute(
        """INSERT INTO refresh_tokens (user_id, token_hash, expires_at, ip_address, user_agent)
           VALUES (:1, :2, TO_TIMESTAMP(:3,'YYYY-MM-DD HH24:MI:SS'), :4, :5)""",
        [user_id, hashed_refresh,
         refresh_expires.strftime("%Y-%m-%d %H:%M:%S"), ip, ua]
    )
    await db.commit()

    # Set HttpOnly cookie for refresh token
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=settings.ENV == "production",
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth",
    )

    return TokenResponse(
        access_token=access_token,
        role=role,
        name=full_name,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: oracledb.AsyncConnection = Depends(get_db),
):
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    hashed = hashlib.sha256(raw_token.encode()).hexdigest()
    cursor = db.cursor()
    await cursor.execute(
        """SELECT rt.id, rt.user_id, rt.expires_at, rt.revoked,
                  u.username, u.full_name, u.role, u.is_active
           FROM refresh_tokens rt
           JOIN users u ON u.id = rt.user_id
           WHERE rt.token_hash = :1""",
        [hashed]
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    rt_id, user_id, expires_at, revoked, username, full_name, role, is_active = row

    if revoked or not is_active:
        raise HTTPException(status_code=401, detail="Token revoked")

    if datetime.now(timezone.utc) > expires_at.replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    # Rotate: revoke old, create new
    await cursor.execute("UPDATE refresh_tokens SET revoked = 1 WHERE id = :1", [rt_id])
    raw_new, hashed_new = create_refresh_token()
    new_expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")[:256]
    await cursor.execute(
        """INSERT INTO refresh_tokens (user_id, token_hash, expires_at, ip_address, user_agent)
           VALUES (:1, :2, TO_TIMESTAMP(:3,'YYYY-MM-DD HH24:MI:SS'), :4, :5)""",
        [user_id, hashed_new, new_expires.strftime("%Y-%m-%d %H:%M:%S"), ip, ua]
    )
    await db.commit()

    token_data = {"sub": str(user_id), "username": username, "role": role, "name": full_name}
    access_token = create_access_token(token_data)

    response.set_cookie("refresh_token", raw_new, httponly=True,
                        secure=settings.ENV == "production", samesite="strict",
                        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, path="/api/auth")

    return TokenResponse(access_token=access_token, role=role, name=full_name,
                         expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    raw_token = request.cookies.get("refresh_token")
    if raw_token:
        hashed = hashlib.sha256(raw_token.encode()).hexdigest()
        cursor =  db.cursor()
        await cursor.execute(
            "UPDATE refresh_tokens SET revoked = 1 WHERE token_hash = :1",
            [hashed]
        )
        await db.commit()

    response.delete_cookie("refresh_token", path="/api/auth")
    return {"message": "Logged out"}


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: oracledb.AsyncConnection = Depends(get_db),
):
    cursor =  db.cursor()
    await cursor.execute("SELECT hashed_pw FROM users WHERE id = :1", [int(current_user["id"])])
    row = await cursor.fetchone()
    if not row or not verify_password(data.current_password, row[0]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    new_hash = hash_password(data.new_password)
    await cursor.execute("UPDATE users SET hashed_pw = :1, updated_at = SYSTIMESTAMP WHERE id = :2",
                         [new_hash, int(current_user["id"])])
    await db.commit()
    return {"message": "Password changed successfully"}


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user
