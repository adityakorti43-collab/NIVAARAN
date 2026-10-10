"""Sign in with Google, Apple, or a one-time code sent to a phone number.

Google and Apple use the OAuth 2.0 authorization-code flow, run entirely on the server:
  /api/auth/{provider}/start  -> stores a single-use, hashed `state` (10 minutes) and redirects to the provider
  /api/auth/{provider}/callback -> checks the state, exchanges the code at the provider's token endpoint and reads
  the ID token. The ID token is received directly from the provider over TLS in that server-to-server exchange, which
  OpenID Connect Core (section 3.1.3.7) allows in place of a signature check; issuer, audience and expiry are still
  verified. Each provider is enabled only when its credentials are configured (see README):
  - Google: NIVAARAN_GOOGLE_CLIENT_ID, NIVAARAN_GOOGLE_CLIENT_SECRET
  - Apple:  NIVAARAN_APPLE_CLIENT_ID (Services ID), NIVAARAN_APPLE_CLIENT_SECRET (the ES256 client-secret JWT generated
            with your Apple key; valid for up to six months)
  Redirect URIs to register with the provider: {NIVAARAN_PUBLIC_URL}/api/auth/google/callback and .../apple/callback.

Phone sign-in: a 6-digit code, stored only as a salted hash, valid for 10 minutes, at most 5 attempts, and at most one
code per 30 seconds and 5 per hour for a number. Delivery uses Twilio when NIVAARAN_TWILIO_ACCOUNT_SID,
NIVAARAN_TWILIO_AUTH_TOKEN and NIVAARAN_TWILIO_FROM are set. Without an SMS provider the code is written to the local
outbox (like password-reset links); only when NIVAARAN_DEV_OTP=1 is it also returned to the browser, for local testing.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from app import store
from app.auth import OUTBOX, User, _row_to_user, USER_COLS, unusable_password
from app.config import log

PUBLIC_URL = os.environ.get("NIVAARAN_PUBLIC_URL", "http://localhost:5173").rstrip("/")
GOOGLE_ID = os.environ.get("NIVAARAN_GOOGLE_CLIENT_ID", "")
GOOGLE_SECRET = os.environ.get("NIVAARAN_GOOGLE_CLIENT_SECRET", "")
APPLE_ID = os.environ.get("NIVAARAN_APPLE_CLIENT_ID", "")
APPLE_SECRET = os.environ.get("NIVAARAN_APPLE_CLIENT_SECRET", "")
TWILIO_SID = os.environ.get("NIVAARAN_TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.environ.get("NIVAARAN_TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.environ.get("NIVAARAN_TWILIO_FROM", "")
DEV_OTP = os.environ.get("NIVAARAN_DEV_OTP", "0") == "1"
OTP_PEPPER = os.environ.get("NIVAARAN_OTP_PEPPER") or secrets.token_hex(16)  # per-process if not configured

PROVIDERS = {
    "google": {"authorize": "https://accounts.google.com/o/oauth2/v2/auth", "token": "https://oauth2.googleapis.com/token",
               "issuers": {"https://accounts.google.com", "accounts.google.com"}},
    "apple": {"authorize": "https://appleid.apple.com/auth/authorize", "token": "https://appleid.apple.com/auth/token",
              "issuers": {"https://appleid.apple.com"}},
}
_sent: dict[str, list[float]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _h(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()


def configured() -> dict:
    sms = "sms" if (TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM) else "outbox"
    return {"google": bool(GOOGLE_ID and GOOGLE_SECRET), "apple": bool(APPLE_ID and APPLE_SECRET),
            "phone": {"enabled": True, "delivery": sms, "dev_codes": DEV_OTP and sms == "outbox"}}


def safe_next(next_: Optional[str]) -> str:
    """Only same-site relative paths are allowed as post-login destinations."""
    if next_ and next_.startswith("/") and not next_.startswith("//") and "\\" not in next_:
        return next_[:300]
    return "/dashboard"


# ----------------------------------------------------------------------------------------------- OAuth (Google/Apple)
def _client(provider: str) -> tuple[str, str]:
    cid, sec = (GOOGLE_ID, GOOGLE_SECRET) if provider == "google" else (APPLE_ID, APPLE_SECRET)
    if not (cid and sec):
        raise HTTPException(status_code=503, detail=f"{provider.title()} sign-in is not configured on this server.")
    return cid, sec


def redirect_uri(provider: str) -> str:
    return f"{PUBLIC_URL}/api/auth/{provider}/callback"


def authorize_url(provider: str, next_: Optional[str]) -> str:
    cid, _ = _client(provider)
    state = secrets.token_urlsafe(32)
    store.execute("DELETE FROM oauth_states WHERE expires < ?", (_now().isoformat(),))
    store.execute("INSERT INTO oauth_states (state_hash, provider, next, expires) VALUES (?,?,?,?)",
                  (_h(state), provider, safe_next(next_), (_now() + timedelta(minutes=10)).isoformat()))
    params = {"client_id": cid, "redirect_uri": redirect_uri(provider), "response_type": "code", "state": state}
    if provider == "google":
        params.update(scope="openid email profile", prompt="select_account")
    else:
        params.update(scope="name email", response_mode="form_post")
    return f"{PROVIDERS[provider]['authorize']}?{urlencode(params)}"


def consume_state(provider: str, state: Optional[str]) -> str:
    if not state:
        raise HTTPException(status_code=400, detail="Sign-in was interrupted. Please try again.")
    rows = store.query("SELECT provider, next, expires FROM oauth_states WHERE state_hash=?", (_h(state),))
    store.execute("DELETE FROM oauth_states WHERE state_hash=?", (_h(state),))   # single use
    if not rows or rows[0][0] != provider or datetime.fromisoformat(rows[0][2]) < _now():
        raise HTTPException(status_code=400, detail="This sign-in link has expired. Please try again.")
    return rows[0][1]


def _claims(id_token: str) -> dict:
    try:
        payload = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="The sign-in provider returned an unreadable response.") from exc


def exchange_code(provider: str, code: str) -> dict:
    """Exchange the authorization code; return verified identity claims (sub, email, email_verified, name)."""
    cid, sec = _client(provider)
    try:
        r = httpx.post(PROVIDERS[provider]["token"], timeout=15, headers={"Accept": "application/json"},
                       data={"grant_type": "authorization_code", "code": code, "client_id": cid, "client_secret": sec,
                             "redirect_uri": redirect_uri(provider)})
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach {provider.title()}. Please try again.") from exc
    if r.status_code != 200 or "id_token" not in r.json():
        log.warning("%s token exchange failed with HTTP %s", provider, r.status_code)
        raise HTTPException(status_code=401, detail=f"{provider.title()} did not confirm the sign-in. Please try again.")
    c = _claims(r.json()["id_token"])
    if c.get("iss") not in PROVIDERS[provider]["issuers"] or c.get("aud") != cid or float(c.get("exp", 0)) < time.time() or not c.get("sub"):
        raise HTTPException(status_code=401, detail="The sign-in response could not be verified.")
    verified = c.get("email_verified") in (True, "true")
    return {"sub": str(c["sub"]), "email": (c.get("email") or "").strip(), "email_verified": verified, "name": c.get("name") or ""}


def _user_where(sql: str, args: tuple) -> Optional[User]:
    rows = store.query(f"SELECT {USER_COLS} FROM users WHERE {sql}", args)
    return _row_to_user(rows[0]) if rows else None


def user_for_identity(provider: str, ident: dict, display_name: str = "") -> User:
    """Find the account linked to this Google/Apple identity, link it to an existing account with the same verified
    email, or create a new account."""
    col = "google_sub" if provider == "google" else "apple_sub"
    u = _user_where(f"{col}=?", (ident["sub"],))
    if u:
        return u
    if ident["email"] and ident["email_verified"]:
        u = _user_where("email=? AND is_demo=0", (ident["email"],))
        if u:
            store.execute(f"UPDATE users SET {col}=? WHERE id=?", (ident["sub"], u.id))
            return u
    email = ident["email"] if ident["email"] and ident["email_verified"] else f"{ident['sub'][:40]}@{provider}.nivaaran.local"
    name = (display_name or ident["name"] or (email.split("@")[0] if "@" in email else "") or "Nivaaran user")[:80]
    uid = f"usr-{uuid.uuid4().hex[:12]}"
    store.execute(f"INSERT INTO users (id, email, name, pw_hash, created, is_demo, provider, {col}) VALUES (?,?,?,?,?,0,?,?)",
                  (uid, email, name, unusable_password(), _now().isoformat(timespec="seconds"), provider, ident["sub"]))
    return _user_where("id=?", (uid,))  # type: ignore[return-value]


# ------------------------------------------------------------------------------------------------ Phone one-time code
def normalise_phone(raw: str) -> str:
    digits = re.sub(r"[\s\-().]", "", raw or "")
    if re.fullmatch(r"[6-9]\d{9}", digits):          # Indian mobile number without a country code
        digits = "+91" + digits
    elif re.fullmatch(r"0[6-9]\d{9}", digits):
        digits = "+91" + digits[1:]
    elif re.fullmatch(r"91[6-9]\d{9}", digits):
        digits = "+" + digits
    if not re.fullmatch(r"\+[1-9]\d{7,14}", digits):
        raise HTTPException(status_code=400, detail="Enter a valid mobile number, for example 98765 43210 or +91 98765 43210.")
    return digits


def _code_hash(phone: str, code: str) -> str:
    return hmac.new(OTP_PEPPER.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def _deliver(phone: str, code: str) -> str:
    body = f"Your Nivaaran sign-in code is {code}. It expires in 10 minutes. Never share it with anyone."
    if TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM:
        try:
            r = httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json", timeout=15,
                           auth=(TWILIO_SID, TWILIO_TOKEN), data={"From": TWILIO_FROM, "To": phone, "Body": body})
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="We couldn't send the text message. Please try again.") from exc
        if r.status_code >= 300:
            log.warning("SMS delivery failed with HTTP %s", r.status_code)
            raise HTTPException(status_code=502, detail="We couldn't send the text message. Please try again.")
        return "sms"
    OUTBOX.mkdir(parents=True, exist_ok=True)
    (OUTBOX / f"sms-{_now().strftime('%Y%m%d-%H%M%S')}-{phone[-4:]}.txt").write_text(f"To: {phone}\n\n{body}\n", encoding="utf-8")
    log.info("Phone sign-in code for ...%s written to outbox (no SMS provider configured)", phone[-4:])
    return "outbox"


def start_phone(raw: str) -> dict:
    phone = normalise_phone(raw)
    now = time.time()
    recent = [t for t in _sent.get(phone, []) if now - t < 3600]
    if recent and now - recent[-1] < 30:
        raise HTTPException(status_code=429, detail="Please wait 30 seconds before requesting another code.")
    if len(recent) >= 5:
        raise HTTPException(status_code=429, detail="Too many codes requested for this number. Try again in an hour.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    store.execute("INSERT OR REPLACE INTO otp_codes (phone, code_hash, expires, attempts, sent) VALUES (?,?,?,0,?)",
                  (phone, _code_hash(phone, code), (_now() + timedelta(minutes=10)).isoformat(), _now().isoformat()))
    _sent[phone] = recent + [now]
    delivery = _deliver(phone, code)
    out = {"phone": phone, "delivery": delivery, "masked": phone[:3] + " ••••• " + phone[-4:]}
    if DEV_OTP and delivery == "outbox":
        out["dev_code"] = code   # local development only (NIVAARAN_DEV_OTP=1); never set this in production
    return out


def verify_phone(raw: str, code: str, name: str = "") -> User:
    phone = normalise_phone(raw)
    rows = store.query("SELECT code_hash, expires, attempts FROM otp_codes WHERE phone=?", (phone,))
    if not rows or datetime.fromisoformat(rows[0][1]) < _now():
        raise HTTPException(status_code=400, detail="This code has expired. Request a new one.")
    if rows[0][2] >= 5:
        store.execute("DELETE FROM otp_codes WHERE phone=?", (phone,))
        raise HTTPException(status_code=429, detail="Too many wrong codes. Request a new one.")
    if not re.fullmatch(r"\d{6}", (code or "").strip()) or not hmac.compare_digest(rows[0][0], _code_hash(phone, code.strip())):
        store.execute("UPDATE otp_codes SET attempts = attempts + 1 WHERE phone=?", (phone,))
        raise HTTPException(status_code=401, detail="That code isn't right. Check the message and try again.")
    store.execute("DELETE FROM otp_codes WHERE phone=?", (phone,))
    u = _user_where("phone=?", (phone,))
    if u:
        return u
    uid = f"usr-{uuid.uuid4().hex[:12]}"
    store.execute("INSERT INTO users (id, email, name, pw_hash, created, is_demo, provider, phone) VALUES (?,?,?,?,?,0,'phone',?)",
                  (uid, f"{phone.lstrip('+')}@phone.nivaaran.local", (name.strip() or "Nivaaran user")[:80], unusable_password(),
                   _now().isoformat(timespec="seconds"), phone))
    return _user_where("id=?", (uid,))  # type: ignore[return-value]
