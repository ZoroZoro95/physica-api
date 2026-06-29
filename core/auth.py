from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import Header, HTTPException

from .db import connect, initialize_auth_schema, placeholder


SESSION_TTL_SECONDS = 60 * 60 * 24 * 14


@dataclass(frozen=True)
class AuthUser:
    sub: str
    email: str
    name: str = ""
    picture: str = ""
    role: str = "student"
    status: str = "active"
    session_id: str = ""
    session_expires_at: str = ""


def verify_google_id_token(id_token: str) -> AuthUser:
    client_id = os.getenv("GOOGLE_CLIENT_ID") or os.getenv("NEXT_PUBLIC_GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID is not configured")
    query = urllib.parse.urlencode({"id_token": id_token})
    url = f"https://oauth2.googleapis.com/tokeninfo?{query}"
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Google token verification failed: {exc}") from exc
    if payload.get("aud") != client_id:
        raise HTTPException(status_code=401, detail="Google token audience mismatch")
    if not payload.get("email"):
        raise HTTPException(status_code=401, detail="Google account has no email")
    return AuthUser(
        sub=str(payload.get("sub") or payload["email"]),
        email=str(payload["email"]),
        name=str(payload.get("name") or ""),
        picture=str(payload.get("picture") or ""),
    )


def create_session_token(user: AuthUser) -> str:
    initialize_auth_schema()
    now = _now()
    expires_at = _iso(_now_dt() + timedelta(seconds=_session_ttl_seconds()))
    stored_user = _upsert_user(user=user, now=now)
    session_id = f"as_{uuid4().hex[:16]}"
    token = f"ps_{session_id}.{secrets.token_urlsafe(32)}"
    p = placeholder()
    with connect() as conn:
        conn.cursor().execute(
            f"""
            INSERT INTO auth_sessions (
                session_id, user_id, token_hash, created_at, expires_at,
                last_seen_at, revoked_at, user_agent, ip_address
            ) VALUES ({", ".join([p] * 9)})
            """,
            [
                session_id,
                stored_user["user_id"],
                _token_hash(token),
                now,
                expires_at,
                now,
                None,
                "",
                "",
            ],
        )
    return token


def verify_session_token(token: str) -> AuthUser:
    initialize_auth_schema()
    p = placeholder()
    with connect() as conn:
        row = conn.cursor().execute(
            f"""
            SELECT
                s.session_id,
                s.expires_at,
                s.revoked_at,
                u.user_id,
                u.email,
                u.name,
                u.picture,
                u.role,
                u.status
            FROM auth_sessions s
            JOIN users u ON u.user_id = s.user_id
            WHERE s.token_hash = {p}
            """,
            [_token_hash(token)],
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid auth token")
    item = _row_dict(row)
    if item.get("revoked_at"):
        raise HTTPException(status_code=401, detail="Auth token revoked")
    if _parse_iso(str(item.get("expires_at") or "")) < _now_dt():
        raise HTTPException(status_code=401, detail="Auth token expired")
    if item.get("status") != "active":
        raise HTTPException(status_code=403, detail="User account is not active")
    _mark_seen(str(item["session_id"]), str(item["user_id"]))
    return AuthUser(
        sub=str(item.get("user_id") or ""),
        email=str(item.get("email") or ""),
        name=str(item.get("name") or ""),
        picture=str(item.get("picture") or ""),
        role=str(item.get("role") or "student"),
        status=str(item.get("status") or "active"),
        session_id=str(item.get("session_id") or ""),
        session_expires_at=str(item.get("expires_at") or ""),
    )


def revoke_session_token(token: str) -> int:
    initialize_auth_schema()
    p = placeholder()
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE auth_sessions SET revoked_at = {p} WHERE token_hash = {p} AND revoked_at IS NULL",
            [_now(), _token_hash(token)],
        )
        return int(cur.rowcount or 0)


def optional_auth_user(authorization: str | None = Header(default=None)) -> AuthUser | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Use Bearer auth token")
    return verify_session_token(token)


def require_auth_user(authorization: str | None = Header(default=None)) -> AuthUser:
    user = optional_auth_user(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in required")
    return user


def public_user_payload(user: AuthUser) -> dict[str, Any]:
    return {
        "sub": user.sub,
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "role": user.role,
        "status": user.status,
        "session_id": user.session_id,
        "session_expires_at": user.session_expires_at,
    }


def _upsert_user(*, user: AuthUser, now: str) -> dict[str, Any]:
    p = placeholder()
    with connect() as conn:
        existing = conn.cursor().execute(
            f"SELECT * FROM users WHERE user_id = {p} OR email = {p} LIMIT 1",
            [user.sub, user.email],
        ).fetchone()
        if existing:
            item = _row_dict(existing)
            conn.cursor().execute(
                f"""
                UPDATE users
                SET provider = {p},
                    provider_sub = {p},
                    email = {p},
                    name = {p},
                    picture = {p},
                    last_login_at = {p},
                    last_seen_at = {p}
                WHERE user_id = {p}
                """,
                [
                    "google",
                    user.sub,
                    user.email,
                    user.name,
                    user.picture,
                    now,
                    now,
                    item["user_id"],
                ],
            )
            return {**item, "email": user.email, "name": user.name, "picture": user.picture}
        conn.cursor().execute(
            f"""
            INSERT INTO users (
                user_id, provider, provider_sub, email, name, picture,
                role, status, created_at, last_login_at, last_seen_at
            ) VALUES ({", ".join([p] * 11)})
            """,
            [
                user.sub,
                "google",
                user.sub,
                user.email,
                user.name,
                user.picture,
                user.role,
                user.status,
                now,
                now,
                now,
            ],
        )
        return {
            "user_id": user.sub,
            "provider": "google",
            "provider_sub": user.sub,
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
            "role": user.role,
            "status": user.status,
            "created_at": now,
            "last_login_at": now,
            "last_seen_at": now,
        }


def _mark_seen(session_id: str, user_id: str) -> None:
    p = placeholder()
    now = _now()
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE auth_sessions SET last_seen_at = {p} WHERE session_id = {p}", [now, session_id])
        cur.execute(f"UPDATE users SET last_seen_at = {p} WHERE user_id = {p}", [now, user_id])


def _secret() -> bytes:
    secret = (
        os.getenv("APP_AUTH_SECRET")
        or os.getenv("AUTH_SECRET")
        or os.getenv("GOOGLE_CLIENT_SECRET")
        or os.getenv("GOOGLE_CLIENT_ID")
    )
    if not secret:
        raise HTTPException(status_code=500, detail="APP_AUTH_SECRET/AUTH_SECRET or GOOGLE_CLIENT_ID is required")
    return secret.encode("utf-8")


def _session_ttl_seconds() -> int:
    raw = os.getenv("SESSION_TTL_SECONDS")
    if not raw:
        return SESSION_TTL_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return SESSION_TTL_SECONDS
    return max(60, value)


def _token_hash(token: str) -> str:
    return hmac.new(_secret(), token.encode("utf-8"), hashlib.sha256).hexdigest()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return _iso(_now_dt())


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def _row_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    return dict(row)
