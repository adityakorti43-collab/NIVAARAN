"""Accounts and sessions.

- Passwords: scrypt (stdlib hashlib), with PBKDF2-SHA256 as a portable fallback; only salted hashes are stored.
- Sessions: 256-bit random tokens in an HttpOnly, SameSite=Lax cookie; the database stores only SHA-256 of the
  token, so a database leak does not reveal live sessions. Server-side expiry; logout deletes the session.
- Password reset: single-use tokens (hashed at rest) that expire after 30 minutes. Email delivery is not
  configured in this build, so reset links are written to a local outbox directory for the operator
  (documented in the README); the API response never reveals whether an email address exists.
- Failed logins are rate-limited per email address.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Cookie, HTTPException, Request, Response
from pydantic import BaseModel

from app import store
from app.config import DATA_DIR, log

COOKIE = "nivaaran_session"
SESSION_DAYS = int(os.environ.get("NIVAARAN_SESSION_DAYS", "7"))
COOKIE_SECURE = os.environ.get("NIVAARAN_COOKIE_SECURE", "0") == "1"  # set to 1 behind HTTPS
OUTBOX = DATA_DIR / "outbox"
PBKDF2_ITERATIONS = 600_000
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,24}$")
_fails: dict[str, list[float]] = {}


class User(BaseModel):
    id: str
    email: str
    name: str
    created: str
    is_demo: bool = False
    phone: Optional[str] = None
    provider: str = "password"   # password | google | apple | phone | demo
    has_password: bool = True


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fallback_derived_key(pw: str, salt: bytes, iterations: int, dklen: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, iterations, dklen=dklen)


def _legacy_fallback_iterations(n: int, r: int, p: int) -> int:
    return max(100_000, (n * r * p) // 2)


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    scrypt = getattr(hashlib, "scrypt", None)
    if callable(scrypt):
        try:
            dk = scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
            return f"scrypt$16384$8$1${salt.hex()}${dk.hex()}"
        except (TypeError, ValueError):
            pass
    dk = _fallback_derived_key(pw, salt, PBKDF2_ITERATIONS, 32)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        parts = stored.split("$")
        if len(parts) == 4 and parts[0] == "pbkdf2_sha256":
            iterations = int(parts[1])
            if not 100_000 <= iterations <= 10_000_000:
                return False
            salt, expected = bytes.fromhex(parts[2]), bytes.fromhex(parts[3])
            got = _fallback_derived_key(pw, salt, iterations, len(expected))
            return hmac.compare_digest(got, expected)

        if len(parts) != 6 or parts[0] != "scrypt":
            return False
        _, n_raw, r_raw, p_raw, salt_raw, expected_raw = parts
        n, r, p = int(n_raw), int(r_raw), int(p_raw)
        if not 2 ** 10 <= n <= 2 ** 20 or n & (n - 1) or not 1 <= r <= 32 or not 1 <= p <= 16:
            return False
        salt, expected = bytes.fromhex(salt_raw), bytes.fromhex(expected_raw)
        scrypt = getattr(hashlib, "scrypt", None)
        if callable(scrypt):
            try:
                got = scrypt(pw.encode(), salt=salt, n=n, r=r, p=p, dklen=len(expected))
                if hmac.compare_digest(got, expected):
                    return True
            except (TypeError, ValueError):
                pass

        # Earlier builds stored PBKDF2 fallback hashes with a scrypt prefix.
        iterations = _legacy_fallback_iterations(n, r, p)
        if iterations > 10_000_000:
            return False
        got = _fallback_derived_key(pw, salt, iterations, len(expected))
        return hmac.compare_digest(got, expected)
    except (ValueError, TypeError):
        return False


def validate_password(pw: str) -> None:
    if len(pw) < 10 or not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        raise HTTPException(status_code=400, detail="Use at least 10 characters, including a letter and a number.")


# Columns every user lookup selects, in this order (pw_hash last).
USER_COLS = "id, email, name, created, is_demo, phone, provider, pw_hash"


def _row_to_user(r) -> User:
    """r = (id, email, name, created, is_demo, phone, provider, pw_hash)."""
    pw = r[7] or ""
    has_password = pw.startswith(("scrypt$", "pbkdf2_sha256$"))
    return User(id=r[0], email=r[1], name=r[2], created=r[3], is_demo=bool(r[4]), phone=r[5],
                provider="demo" if r[4] else (r[6] or "password"), has_password=has_password)


def unusable_password() -> str:
    """Accounts created through Google, Apple or a phone code have no password; this value never verifies."""
    return "!" + secrets.token_hex(16)


def get_user_by_email(email: str) -> Optional[tuple]:
    rows = store.query(f"SELECT {USER_COLS} FROM users WHERE email=?", (email.strip(),))
    return rows[0] if rows else None


def create_user(email: str, name: str, password: str, is_demo: bool = False) -> User:
    email = email.strip()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    if not name.strip() or len(name) > 80:
        raise HTTPException(status_code=400, detail="Enter your name (up to 80 characters).")
    if not is_demo:
        validate_password(password)
    if get_user_by_email(email):
        raise HTTPException(status_code=409, detail="An account with this email already exists. Sign in instead.")
    uid = f"usr-{uuid.uuid4().hex[:12]}"
    created = _now().isoformat(timespec="seconds")
    store.execute("INSERT INTO users (id, email, name, pw_hash, created, is_demo) VALUES (?,?,?,?,?,?)",
                  (uid, email, name.strip(), hash_password(password), created, int(is_demo)))
    return User(id=uid, email=email, name=name.strip(), created=created, is_demo=is_demo, provider="demo" if is_demo else "password")


def authenticate(email: str, password: str) -> User:
    key = email.strip().lower()
    recent = [t for t in _fails.get(key, []) if time.time() - t < 900]
    if len(recent) >= 5:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
    row = get_user_by_email(email)
    if not row or row[4] or not verify_password(password, row[7]):
        _fails[key] = recent + [time.time()]
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    _fails.pop(key, None)
    return _row_to_user(row)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(response: Response, user_id: str, days: int = SESSION_DAYS) -> None:
    token = secrets.token_urlsafe(32)
    now = _now()
    store.execute("INSERT INTO sessions (token_hash, user_id, created, expires) VALUES (?,?,?,?)",
                  (_token_hash(token), user_id, now.isoformat(), (now + timedelta(days=days)).isoformat()))
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
    if datetime.fromisoformat(rows[0][8]) < _now():
        store.execute("DELETE FROM sessions WHERE token_hash=?", (_token_hash(token),))
        return None
    return _row_to_user(rows[0])


def require_user(request: Request, nivaaran_session: Optional[str] = Cookie(default=None)) -> User:
    """FastAPI dependency: every protected endpoint resolves the user on the server from the session cookie."""
    u = user_from_token(nivaaran_session)
    if not u:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    request.state.user = u
    return u


def request_reset(email: str) -> None:
    row = get_user_by_email(email)
    if not row or row[4]:
        return  # never reveal whether the account exists
    token = secrets.token_urlsafe(32)
    store.execute("INSERT INTO reset_tokens (token_hash, user_id, expires) VALUES (?,?,?)",
                  (_token_hash(token), row[0], (_now() + timedelta(minutes=30)).isoformat()))
    OUTBOX.mkdir(parents=True, exist_ok=True)
    (OUTBOX / f"reset-{_now().strftime('%Y%m%d-%H%M%S')}-{row[0]}.txt").write_text(
        f"To: {row[1]}\nSubject: Reset your Nivaaran password\n\nOpen this link within 30 minutes:\n"
        f"http://localhost:5173/reset-password?token={token}\n", encoding="utf-8")
    log.info("Password reset requested for user %s (email delivery not configured; link written to outbox)", row[0])


def confirm_reset(token: str, new_password: str) -> None:
    validate_password(new_password)
    rows = store.query("SELECT user_id, expires, used FROM reset_tokens WHERE token_hash=?", (_token_hash(token),))
    if not rows or rows[0][2] or datetime.fromisoformat(rows[0][1]) < _now():
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired. Request a new one.")
    uid = rows[0][0]
    store.execute("UPDATE users SET pw_hash=? WHERE id=?", (hash_password(new_password), uid))
    store.execute("UPDATE reset_tokens SET used=1 WHERE token_hash=?", (_token_hash(token),))
    store.execute("DELETE FROM sessions WHERE user_id=?", (uid,))  # sign out everywhere


def change_password(user: User, current: str, new: str) -> None:
    row = get_user_by_email(user.email)
    if not row or not verify_password(current, row[7]):
        raise HTTPException(status_code=400, detail="Your current password is incorrect.")
    validate_password(new)
    store.execute("UPDATE users SET pw_hash=? WHERE id=?", (hash_password(new), user.id))


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
