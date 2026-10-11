"""SQLite persistence (stdlib sqlite3) with versioned migrations, per-user ownership and auth tables.

Domain objects are stored as validated JSON payloads alongside indexed relational columns (owner, claim,
timestamps) so every query can be filtered by owner. Uploaded bytes live under random IDs in a private
directory; internal paths are never returned by the API.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from app.config import DB_PATH, UPLOAD_DIR, ensure_dirs
from app.models import AnalysisResult, Claim, DocumentRecord

_lock = threading.Lock()
_migrated = False

MIGRATIONS = [
    # v1 — original tables
    """
    CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, doc_type TEXT, created TEXT, payload TEXT);
    CREATE TABLE IF NOT EXISTS claims (id TEXT PRIMARY KEY, created TEXT, payload TEXT);
    CREATE TABLE IF NOT EXISTS analyses (id TEXT PRIMARY KEY, claim_id TEXT, created TEXT, payload TEXT);
    CREATE TABLE IF NOT EXISTS comparisons (id TEXT PRIMARY KEY, claim_id TEXT, created TEXT, payload TEXT);
    CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, payload TEXT);
    """,
    # v2 — accounts, ownership, saved scenarios, chat history, generated reports
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE, name TEXT NOT NULL, pw_hash TEXT NOT NULL,
        created TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created TEXT NOT NULL, expires TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS reset_tokens (
        token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS scenarios (
        id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, owner_id TEXT NOT NULL, created TEXT NOT NULL, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS chats (
        id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, owner_id TEXT NOT NULL, created TEXT NOT NULL, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS reports (
        id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, owner_id TEXT NOT NULL, created TEXT NOT NULL, kind TEXT NOT NULL,
        analysis_id TEXT NOT NULL, bytes INTEGER NOT NULL);
    ALTER TABLE documents ADD COLUMN owner_id TEXT;
    ALTER TABLE claims ADD COLUMN owner_id TEXT;
    CREATE INDEX IF NOT EXISTS ix_documents_owner ON documents(owner_id);
    CREATE INDEX IF NOT EXISTS ix_claims_owner ON claims(owner_id);
    CREATE INDEX IF NOT EXISTS ix_analyses_claim ON analyses(claim_id);
    CREATE INDEX IF NOT EXISTS ix_comparisons_claim ON comparisons(claim_id);
    CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions(user_id);
    CREATE INDEX IF NOT EXISTS ix_scenarios_claim ON scenarios(claim_id, owner_id);
    CREATE INDEX IF NOT EXISTS ix_chats_claim ON chats(claim_id, owner_id);
    CREATE INDEX IF NOT EXISTS ix_reports_owner ON reports(owner_id);
    """,
    # v3 — sign-in with Google, Apple and phone number (one-time codes); OAuth state is kept server-side
    """
    ALTER TABLE users ADD COLUMN phone TEXT;
    ALTER TABLE users ADD COLUMN google_sub TEXT;
    ALTER TABLE users ADD COLUMN apple_sub TEXT;
    ALTER TABLE users ADD COLUMN provider TEXT NOT NULL DEFAULT 'password';
    CREATE UNIQUE INDEX IF NOT EXISTS ux_users_phone ON users(phone) WHERE phone IS NOT NULL;
    CREATE UNIQUE INDEX IF NOT EXISTS ux_users_google ON users(google_sub) WHERE google_sub IS NOT NULL;
    CREATE UNIQUE INDEX IF NOT EXISTS ux_users_apple ON users(apple_sub) WHERE apple_sub IS NOT NULL;
    CREATE TABLE IF NOT EXISTS otp_codes (
        phone TEXT PRIMARY KEY, code_hash TEXT NOT NULL, expires TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, sent TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS oauth_states (
        state_hash TEXT PRIMARY KEY, provider TEXT NOT NULL, next TEXT NOT NULL, expires TEXT NOT NULL)
    """,
]



def _v4_users(c: sqlite3.Connection) -> None:
    """v4 — accounts are identities (Google subject, verified phone), not passwords. Email and name become optional, so
    a phone-only account stores NULL instead of an invented address or name. Adds avatar, verification and timestamps.
    Placeholder values written by earlier versions are cleared."""
    c.commit()
    c.execute("PRAGMA foreign_keys = OFF")
    c.executescript("""
    BEGIN;
    CREATE TABLE users_v4 (
        id TEXT PRIMARY KEY,
        email TEXT COLLATE NOCASE,
        email_verified INTEGER NOT NULL DEFAULT 0,
        name TEXT,
        avatar_url TEXT,
        phone TEXT,
        google_sub TEXT,
        apple_sub TEXT,
        pw_hash TEXT,
        provider TEXT NOT NULL DEFAULT 'password',
        is_demo INTEGER NOT NULL DEFAULT 0,
        created TEXT NOT NULL,
        updated_at TEXT,
        last_login_at TEXT);
    INSERT INTO users_v4 (id, email, email_verified, name, phone, google_sub, apple_sub, pw_hash, provider, is_demo, created, updated_at)
        SELECT id,
               CASE WHEN email LIKE '%.nivaaran.local' THEN NULL ELSE email END,
               CASE WHEN google_sub IS NOT NULL AND email NOT LIKE '%.nivaaran.local' THEN 1 ELSE 0 END,
               CASE WHEN name IN ('Nivaaran user', '') THEN NULL ELSE name END,
               phone, google_sub, apple_sub, pw_hash, provider, is_demo, created, created
        FROM users;
    DROP TABLE users;
    ALTER TABLE users_v4 RENAME TO users;
    CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email ON users(email) WHERE email IS NOT NULL;
    CREATE UNIQUE INDEX IF NOT EXISTS ux_users_phone ON users(phone) WHERE phone IS NOT NULL;
    CREATE UNIQUE INDEX IF NOT EXISTS ux_users_google ON users(google_sub) WHERE google_sub IS NOT NULL;
    CREATE UNIQUE INDEX IF NOT EXISTS ux_users_apple ON users(apple_sub) WHERE apple_sub IS NOT NULL;
    CREATE TABLE IF NOT EXISTS login_links (
        token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0);
    ALTER TABLE oauth_states ADD COLUMN code_verifier TEXT;
    ALTER TABLE oauth_states ADD COLUMN link_user_id TEXT;
    DROP TABLE IF EXISTS otp_codes;
    COMMIT;
    """)
    bad = c.execute("PRAGMA foreign_key_check").fetchall()
    c.execute("PRAGMA foreign_keys = ON")
    if bad:
        raise RuntimeError(f"Foreign key check failed after the users migration: {bad[:3]}")


MIGRATIONS.append(_v4_users)

def _migrate(c: sqlite3.Connection) -> None:
    ver = c.execute("PRAGMA user_version").fetchone()[0]
    for i, sql in enumerate(MIGRATIONS[ver:], start=ver + 1):
        if callable(sql):
            sql(c)
        else:
            for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
                try:
                    c.execute(stmt)
                except sqlite3.OperationalError as e:
                    if "duplicate column" not in str(e):
                        raise
        c.execute(f"PRAGMA user_version = {i}")
        c.commit()


def _conn() -> sqlite3.Connection:
    global _migrated
    ensure_dirs()
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.execute("PRAGMA foreign_keys = ON")
    if not _migrated:
        _migrate(c)
        c.commit()
        _migrated = True
    return c


def execute(sql: str, args: tuple = ()) -> int:
    with _lock, _conn() as c:
        return c.execute(sql, args).rowcount


def query(sql: str, args: tuple = ()) -> list[tuple]:
    with _lock, _conn() as c:
        return c.execute(sql, args).fetchall()


def _put(table: str, id_: str, payload: str, **cols) -> None:
    keys = ["id", *cols.keys(), "payload"]
    execute(f"INSERT OR REPLACE INTO {table} ({','.join(keys)}) VALUES ({','.join('?' * len(keys))})",
            (id_, *cols.values(), payload))


def _get(table: str, id_: str) -> Optional[str]:
    rows = query(f"SELECT payload FROM {table} WHERE id=?", (id_,))
    return rows[0][0] if rows else None


# ------------------------------------------------------------------ documents

def save_document(doc: DocumentRecord, data: Optional[bytes] = None) -> None:
    if data is not None:
        ensure_dirs()
        (UPLOAD_DIR / f"{doc.document_id}.bin").write_bytes(data)
    _put("documents", doc.document_id, doc.model_dump_json(), doc_type=doc.doc_type.value, created=doc.uploaded_at, owner_id=doc.owner_id)


def get_document(doc_id: str) -> Optional[DocumentRecord]:
    p = _get("documents", doc_id)
    return DocumentRecord.model_validate_json(p) if p else None


def list_documents(owner_id: str) -> list[DocumentRecord]:
    return [DocumentRecord.model_validate_json(r[0]) for r in query("SELECT payload FROM documents WHERE owner_id=? ORDER BY created", (owner_id,))]


def delete_document(doc_id: str) -> bool:
    """Deletes the database record and the stored upload bytes (plain file deletion; no secure wipe)."""
    f = UPLOAD_DIR / f"{doc_id}.bin"
    if f.exists():
        f.unlink()
    return execute("DELETE FROM documents WHERE id=?", (doc_id,)) > 0


# ------------------------------------------------------------------ claims & analyses

def save_claim(claim: Claim) -> None:
    _put("claims", claim.claim_id, claim.model_dump_json(), created=claim.created_at, owner_id=claim.owner_id)


def get_claim(cid: str) -> Optional[Claim]:
    p = _get("claims", cid)
    return Claim.model_validate_json(p) if p else None


def list_claims(owner_id: str) -> list[Claim]:
    return [Claim.model_validate_json(r[0]) for r in query("SELECT payload FROM claims WHERE owner_id=? ORDER BY created", (owner_id,))]


def delete_claim(cid: str) -> None:
    for t, col in (("claims", "id"), ("analyses", "claim_id"), ("comparisons", "claim_id"), ("scenarios", "claim_id"),
                   ("chats", "claim_id"), ("reports", "claim_id")):
        execute(f"DELETE FROM {t} WHERE {col}=?", (cid,))


def save_analysis(a: AnalysisResult) -> None:
    _put("analyses", a.analysis_id, a.model_dump_json(), claim_id=a.claim_id, created=a.created_at)


def get_analysis(aid: str) -> Optional[AnalysisResult]:
    p = _get("analyses", aid)
    return AnalysisResult.model_validate_json(p) if p else None


def list_analyses(claim_id: str) -> list[AnalysisResult]:
    return [AnalysisResult.model_validate_json(r[0]) for r in query("SELECT payload FROM analyses WHERE claim_id=? ORDER BY rowid", (claim_id,))]


def save_comparison(cid: str, claim_id: str, created: str, payload: dict) -> None:
    _put("comparisons", cid, json.dumps(payload, default=str), claim_id=claim_id, created=created)


def list_comparisons(claim_id: str) -> list[dict]:
    return [json.loads(r[0]) for r in query("SELECT payload FROM comparisons WHERE claim_id=? ORDER BY rowid", (claim_id,))]


# ------------------------------------------------------------------ scenarios, chats, reports (owner-scoped)

def save_row(table: str, id_: str, claim_id: str, owner_id: str, created: str, payload: dict) -> None:
    assert table in ("scenarios", "chats")
    _put(table, id_, json.dumps(payload, default=str), claim_id=claim_id, owner_id=owner_id, created=created)


def list_rows(table: str, claim_id: str, owner_id: str) -> list[dict]:
    assert table in ("scenarios", "chats")
    return [json.loads(r[0]) | {"id": r[1], "created": r[2]} for r in
            query(f"SELECT payload, id, created FROM {table} WHERE claim_id=? AND owner_id=? ORDER BY rowid", (claim_id, owner_id))]


def delete_row(table: str, id_: str, owner_id: str) -> bool:
    assert table in ("scenarios", "chats")
    return execute(f"DELETE FROM {table} WHERE id=? AND owner_id=?", (id_, owner_id)) > 0


def record_report(id_: str, claim_id: str, owner_id: str, created: str, kind: str, analysis_id: str, size: int) -> None:
    execute("INSERT INTO reports (id, claim_id, owner_id, created, kind, analysis_id, bytes) VALUES (?,?,?,?,?,?,?)",
            (id_, claim_id, owner_id, created, kind, analysis_id, size))


def list_reports(owner_id: str) -> list[dict]:
    return [dict(zip(("id", "claim_id", "created", "kind", "analysis_id", "bytes"), r)) for r in
            query("SELECT id, claim_id, created, kind, analysis_id, bytes FROM reports WHERE owner_id=? ORDER BY created DESC", (owner_id,))]


def kv_set(k: str, payload: dict) -> None:
    execute("INSERT OR REPLACE INTO kv (k, payload) VALUES (?, ?)", (k, json.dumps(payload, default=str)))


def kv_get(k: str) -> Optional[dict]:
    rows = query("SELECT payload FROM kv WHERE k=?", (k,))
    return json.loads(rows[0][0]) if rows else None


def delete_user_data(owner_id: str) -> None:
    for c in list_claims(owner_id):
        delete_claim(c.claim_id)
    for d in list_documents(owner_id):
        delete_document(d.document_id)
    execute("DELETE FROM reports WHERE owner_id=?", (owner_id,))


def reset_all() -> None:
    for t in ("documents", "claims", "analyses", "comparisons", "kv", "scenarios", "chats", "reports", "sessions", "reset_tokens", "users"):
        execute(f"DELETE FROM {t}")
    for f in UPLOAD_DIR.glob("*.bin"):
        f.unlink()
