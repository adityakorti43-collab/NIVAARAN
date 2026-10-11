"""Sign-in with Google. This is the only way to sign in.

GOOGLE (OpenID Connect authorization-code flow with PKCE, run on the server)
  /api/auth/google/start    stores a single-use, hashed `state` (10 min) with a PKCE verifier and redirects to Google.
  /api/auth/google/callback checks the state, exchanges the code (with the verifier) at Google's token endpoint and
                            reads the ID token from that server-to-server TLS response (OpenID Connect Core 3.1.3.7
                            allows this in place of a signature check). Issuer, audience, expiry and subject are verified.
  The Google subject (`sub`) is the account identity. A new Google identity gets its own account: it is never merged into
  another account because an email matches. Attaching Google to an existing account (for example one opened with an
  operator sign-in link) happens only from inside that account's signed-in session (`?link=1`), which proves ownership.
  Configure: NIVAARAN_GOOGLE_CLIENT_ID, NIVAARAN_GOOGLE_CLIENT_SECRET, NIVAARAN_PUBLIC_URL; register the redirect URI
  {NIVAARAN_PUBLIC_URL}/api/auth/google/callback in Google Cloud Console.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from app import store
from app.auth import User, get_user, insert_user, now_iso
from app.config import log

PUBLIC_URL = os.environ.get("NIVAARAN_PUBLIC_URL", "http://localhost:5173").rstrip("/")
GOOGLE_ID = os.environ.get("NIVAARAN_GOOGLE_CLIENT_ID", "")
GOOGLE_SECRET = os.environ.get("NIVAARAN_GOOGLE_CLIENT_SECRET", "")
GOOGLE_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _h(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()


def configured() -> dict:
    return {"google": bool(GOOGLE_ID and GOOGLE_SECRET)}


def safe_next(next_: Optional[str]) -> str:
    """Only same-site relative paths are allowed as post-login destinations."""
    if next_ and next_.startswith("/") and not next_.startswith("//") and "\\" not in next_:
        return next_[:300]
    return "/dashboard"


# =================================================================================================== Google
def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


# Other public addresses this same server is reachable at (e.g. a temporary tunnel used to test the phone app).
# Google sign-in returns to whichever approved address it started from; each must be registered in Google Cloud.
EXTRA_URLS = [u.strip().rstrip("/") for u in os.environ.get("NIVAARAN_EXTRA_PUBLIC_URLS", "").split(",") if u.strip()]
PUBLIC_URLS = [PUBLIC_URL, *EXTRA_URLS]


def base_for(request_base: Optional[str]) -> str:
    """The approved public address matching the request, else the main one."""
    b = (request_base or "").rstrip("/")
    return b if b in PUBLIC_URLS else PUBLIC_URL


def redirect_uri(base: Optional[str] = None) -> str:
    return f"{base or PUBLIC_URL}/api/auth/google/callback"


# The phone apps (Android/iOS) open Google in the system browser, because Google blocks sign-in inside app web views.
# After Google, the server hands a single-use sign-in link back to the app through this URL scheme.
APP_SCHEME = os.environ.get("NIVAARAN_APP_SCHEME", "in.nivaaran.app")


def authorize_url(next_: Optional[str], link_user: Optional[User] = None, app: bool = False, base: Optional[str] = None) -> str:
    if not (GOOGLE_ID and GOOGLE_SECRET):
        raise HTTPException(status_code=503, detail="Google sign-in isn't set up on this server yet.")
    state = secrets.token_urlsafe(32)
    verifier, challenge = _pkce_pair()
    store.execute("DELETE FROM oauth_states WHERE expires < ?", (_now().isoformat(),))
    store.execute("INSERT INTO oauth_states (state_hash, provider, next, expires, code_verifier, link_user_id) VALUES (?,?,?,?,?,?)",
                  (_h(state), "google-app" if app else "google", safe_next(next_), (_now() + timedelta(minutes=10)).isoformat(), verifier,
                   link_user.id if link_user else None))
    params = {"client_id": GOOGLE_ID, "redirect_uri": redirect_uri(base), "response_type": "code", "scope": "openid email profile",
              "state": state, "prompt": "select_account", "code_challenge": challenge, "code_challenge_method": "S256"}
    return f"{GOOGLE_AUTHORIZE}?{urlencode(params)}"


@dataclass
class OAuthState:
    next: str
    verifier: str
    link_user_id: Optional[str]
    app: bool = False


def consume_state(state: Optional[str]) -> OAuthState:
    if not state:
        raise HTTPException(status_code=400, detail="Sign-in was interrupted. Please try again.")
    rows = store.query("SELECT provider, next, expires, code_verifier, link_user_id FROM oauth_states WHERE state_hash=?", (_h(state),))
    store.execute("DELETE FROM oauth_states WHERE state_hash=?", (_h(state),))   # single use
    if not rows or rows[0][0] not in ("google", "google-app") or datetime.fromisoformat(rows[0][2]) < _now():
        raise HTTPException(status_code=400, detail="This sign-in attempt has expired. Please try again.")
    return OAuthState(next=rows[0][1], verifier=rows[0][3] or "", link_user_id=rows[0][4], app=rows[0][0] == "google-app")


def _claims(id_token: str) -> dict:
    try:
        payload = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Google returned an unreadable response. Please try again.") from exc


def exchange_code(code: str, verifier: str, base: Optional[str] = None) -> dict:
    """Exchange the authorization code; return the verified identity (sub, email, email_verified, name, picture)."""
    if not (GOOGLE_ID and GOOGLE_SECRET):
        raise HTTPException(status_code=503, detail="Google sign-in isn't set up on this server yet.")
    try:
        r = httpx.post(GOOGLE_TOKEN, timeout=15, headers={"Accept": "application/json"},
                       data={"grant_type": "authorization_code", "code": code, "client_id": GOOGLE_ID, "client_secret": GOOGLE_SECRET,
                             "redirect_uri": redirect_uri(base), "code_verifier": verifier})
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Couldn't reach Google. Check your connection and try again.") from exc
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code != 200 or "id_token" not in body:
        log.warning("Google token exchange failed with HTTP %s (%s)", r.status_code, body.get("error"))
        if body.get("error") in ("invalid_client", "unauthorized_client", "redirect_uri_mismatch"):
            raise HTTPException(status_code=503, detail="Google sign-in is misconfigured on this server (client or redirect URI).")
        raise HTTPException(status_code=401, detail="Google didn't confirm the sign-in. Please try again.")
    c = _claims(body["id_token"])
    if c.get("iss") not in GOOGLE_ISSUERS or c.get("aud") != GOOGLE_ID or float(c.get("exp", 0)) < time.time() or not c.get("sub"):
        raise HTTPException(status_code=401, detail="The Google sign-in response could not be verified.")
    verified = c.get("email_verified") in (True, "true")
    return {"sub": str(c["sub"]), "email": (c.get("email") or "").strip() or None, "email_verified": verified,
            "name": (c.get("name") or "").strip() or None, "picture": c.get("picture") or None}


def google_user(ident: dict, link_user_id: Optional[str]) -> User:
    """Return the account for this Google identity: the linked account, the account being linked, or a new one."""
    existing = get_user("google_sub=?", (ident["sub"],))
    if link_user_id:
        if existing and existing.id != link_user_id:
            raise HTTPException(status_code=409, detail="This Google account is already linked to a different Nivaaran account.")
        target = get_user("id=?", (link_user_id,))
        if not target:
            raise HTTPException(status_code=400, detail="Your session ended before linking finished. Please sign in and try again.")
        email = ident["email"] if ident["email_verified"] else None
        clash = get_user("email=? AND id<>?", (email, target.id)) if email else None
        store.execute("UPDATE users SET google_sub=?, email=COALESCE(email, ?), email_verified=CASE WHEN email IS NULL OR email=? THEN ? ELSE email_verified END, "
                      "avatar_url=COALESCE(avatar_url, ?), name=COALESCE(name, ?), updated_at=? WHERE id=?",
                      (ident["sub"], None if clash else email, email, int(bool(email) and not clash), ident["picture"], ident["name"], now_iso(), target.id))
        return get_user("id=?", (target.id,))  # type: ignore[return-value]
    if existing:
        store.execute("UPDATE users SET avatar_url=COALESCE(?, avatar_url), updated_at=? WHERE id=?", (ident["picture"], now_iso(), existing.id))
        return existing
    email = ident["email"] if ident["email_verified"] else None
    if email and get_user("email=?", (email,)):
        email = None   # the address belongs to another account; do not merge, do not duplicate it
    return insert_user({"google_sub": ident["sub"], "email": email, "email_verified": int(bool(email)), "name": ident["name"],
                        "avatar_url": ident["picture"], "provider": "google"}, "google_sub=?", (ident["sub"],))
