"""Accounts and sessions.

Accounts are identities, not passwords: a user signs in with Google (verified Google subject) or with a phone number
verified by an SMS verification provider (see app/social.py). There is no password login.

- Sessions: 256-bit random tokens in an HttpOnly, SameSite=Lax cookie (Secure behind HTTPS); the database stores only
  the SHA-256 of each token, so a database leak does not reveal live sessions. Server-side expiry; logout deletes the
  session row, so a copied cookie stops working immediately.
- Every private endpoint resolves the user from the session on the server (`require_user`); a user id sent by the
  browser is never trusted.
- Profile fields that a provider did not supply (a phone-only account has no email; Google may not share a picture)
  are stored as NULL, never invented.
- Operator one-time sign-in links (`python -m app.manage login-link ...`) let someone with shell access to the server
  open an existing account, for example before any sign-in provider has been configured. They expire after 15 minutes,
  work once, and are not offered anywhere on the website.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Cookie, HTTPException, Request, Response
from pydantic import BaseModel

from app import store
from app.config import DATA_DIR

COOKIE = "nivaaran_session"
SESSION_DAYS = int(os.environ.get("NIVAARAN_SESSION_DAYS", "7"))
COOKIE_SECURE = os.environ.get("NIVAARAN_COOKIE_SECURE", "0") == "1"  # set to 1 behind HTTPS
OUTBOX = DATA_DIR / "outbox"


class User(BaseModel):
    id: str
    email: Optional[str] = None
    email_verified: bool = False
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    google_linked: bool = False
    created: str
    is_demo: bool = False
    provider: str = "phone"   # how the account was first created: google | phone | password (legacy) | demo


USER_COLS = "id, email, email_verified, name, avatar_url, phone, google_sub, created, is_demo, provider"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return _now().isoformat(timespec="seconds")


def _row_to_user(r) -> User:
    return User(id=r[0], email=r[1], email_verified=bool(r[2]), name=r[3], avatar_url=r[4], phone=r[5], google_linked=bool(r[6]),
                created=r[7], is_demo=bool(r[8]), provider="demo" if r[8] else (r[9] or "phone"))


def get_user(where: str, args: tuple) -> Optional[User]:
    rows = store.query(f"SELECT {USER_COLS} FROM users WHERE {where}", args)
    return _row_to_user(rows[0]) if rows else None


def insert_user(fields: dict, unique_where: str, unique_args: tuple) -> User:
    """Create a user row; if a concurrent request created the same identity first, return that row instead."""
    uid = f"usr-{uuid.uuid4().hex[:12]}"
    cols = {"id": uid, "created": now_iso(), "updated_at": now_iso(), **fields}
    try:
        store.execute(f"INSERT INTO users ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})", tuple(cols.values()))
    except sqlite3.IntegrityError:
        existing = get_user(unique_where, unique_args)
        if existing:
            return existing
        raise
    return get_user("id=?", (uid,))  # type: ignore[return-value]


def create_test_user(name: str, is_demo: bool = False) -> User:
    """Internal: accounts for the test-only demo endpoints. Not reachable from the website in production."""
    return insert_user({"name": name, "is_demo": int(is_demo), "provider": "demo" if is_demo else "phone"}, "id=?", ("",))


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(response: Response, user_id: str, days: int = SESSION_DAYS) -> None:
    token = secrets.token_urlsafe(32)
    now = _now()
    store.execute("INSERT INTO sessions (token_hash, user_id, created, expires) VALUES (?,?,?,?)",
                  (_token_hash(token), user_id, now.isoformat(), (now + timedelta(days=days)).isoformat()))
    store.execute("UPDATE users SET last_login_at=? WHERE id=?", (now_iso(), user_id))
    response.set_cookie(COOKIE, token, max_age=days * 86400, httponly=True, samesite="lax", secure=COOKIE_SECURE, path="/")


def end_session(response: Response, token: Optional[str]) -> None:
    if token:
        store.execute("DELETE FROM sessions WHERE token_hash=?", (_token_hash(token),))
    response.delete_cookie(COOKIE, path="/")


def user_from_token(token: Optional[str]) -> Optional[User]:
    if not token:
        return None
    cols = ", ".join(f"u.{c.strip()}" for c in USER_COLS.split(","))
    rows = store.query(f"SELECT {cols}, s.expires FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash=?", (_token_hash(token),))
    if not rows:
        return None
    if datetime.fromisoformat(rows[0][10]) < _now():
        store.execute("DELETE FROM sessions WHERE token_hash=?", (_token_hash(token),))
        return None
    return _row_to_user(rows[0])


def require_user(request: Request, nivaaran_session: Optional[str] = Cookie(default=None)) -> User:
    """FastAPI dependency: every protected endpoint resolves the user on the server from the session cookie."""
    u = user_from_token(nivaaran_session)
    if not u:
        raise HTTPException(status_code=401, detail="Your session has ended. Please sign in again.")
    request.state.user = u
    return u


def update_profile(user: User, name: Optional[str]) -> User:
    clean = (name or "").strip() or None
    if clean and len(clean) > 80:
        raise HTTPException(status_code=400, detail="Use a name of up to 80 characters.")
    store.execute("UPDATE users SET name=?, updated_at=? WHERE id=?", (clean, now_iso(), user.id))
    return get_user("id=?", (user.id,))  # type: ignore[return-value]


def delete_account(user: User) -> None:
    store.delete_user_data(user.id)
    store.execute("DELETE FROM users WHERE id=?", (user.id,))


def cleanup_demo_users(max_age_hours: int = 24) -> int:
    cutoff = (_now() - timedelta(hours=max_age_hours)).isoformat()
    rows = store.query("SELECT id FROM users WHERE is_demo=1 AND created < ?", (cutoff,))
    for (uid,) in rows:
        store.delete_user_data(uid)
        store.execute("DELETE FROM users WHERE id=?", (uid,))
    return len(rows)


# ------------------------------------------------------------------ operator one-time sign-in links
def create_login_link(user_id: str, minutes: int = 15) -> str:
    token = secrets.token_urlsafe(32)
    store.execute("INSERT INTO login_links (token_hash, user_id, expires) VALUES (?,?,?)",
                  (_token_hash(token), user_id, (_now() + timedelta(minutes=minutes)).isoformat()))
    return token


def consume_login_link(token: str) -> Optional[str]:
    rows = store.query("SELECT user_id, expires, used FROM login_links WHERE token_hash=?", (_token_hash(token),))
    if not rows or rows[0][2] or datetime.fromisoformat(rows[0][1]) < _now():
        return None
    store.execute("UPDATE login_links SET used=1 WHERE token_hash=?", (_token_hash(token),))
    return rows[0][0]
