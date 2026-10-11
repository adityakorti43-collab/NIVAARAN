"""Operator commands (run on the server, from the backend directory).

    python -m app.manage users                      list accounts (id, sign-in methods, created)
    python -m app.manage login-link <email|phone|id> print a one-time sign-in link for an existing account (15 minutes)

A sign-in link is for the operator: for example to open an account before Google sign-in has been configured,
or to reach an account created before the move to Google sign-in so a sign-in method can be linked in Settings.
It needs shell access to the server and is not offered anywhere on the website.
"""
from __future__ import annotations

import sys

from app import env  # noqa: F401
from app import auth, store
from app.social import PUBLIC_URL


def _find(key: str):
    if key.startswith("usr-"):
        return auth.get_user("id=?", (key,))
    if "@" in key:
        return auth.get_user("email=?", (key,))
    digits = "".join(ch for ch in key if ch.isdigit())   # older accounts created by phone sign-in
    return auth.get_user("phone=?", (f"+91{digits}" if len(digits) == 10 else f"+{digits}",))


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "users":
        for r in store.query("SELECT id, email, phone, google_sub IS NOT NULL, provider, created FROM users WHERE is_demo=0 ORDER BY created"):
            methods = "google" if r[3] else "Google not linked"
            print(f"{r[0]}  email={r[1] or '-'}  phone={r[2] or '-'}  sign-in: {methods}  (created {r[5]})")
        return 0
    if argv[0] == "login-link" and len(argv) == 2:
        u = _find(argv[1])
        if not u:
            print("No account found for", argv[1])
            return 1
        print(f"{PUBLIC_URL}/api/auth/login-link?token={auth.create_login_link(u.id)}")
        print("Single use, valid for 15 minutes.")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
