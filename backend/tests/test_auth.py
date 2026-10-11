"""Accounts, sessions, profiles and user-to-user isolation. Sign-in itself (Google) is tested in test_signin.py;
these tests get a signed-in client from the test-only /api/demo/user fixture endpoint."""
import time

import pytest
from fastapi.testclient import TestClient

from app import store
from app.main import app


def _msg(r) -> str:
    b = r.json()
    return str(b.get("message") or b.get("detail") or "")


def new_user(name: str = "Asha") -> TestClient:
    c = TestClient(app)
    r = c.post("/api/demo/user", params={"name": name})
    assert r.status_code == 200, r.text
    return c


def test_password_and_apple_sign_in_no_longer_exist():
    c = TestClient(app)
    for path in ("/api/auth/register", "/api/auth/login", "/api/auth/reset/request", "/api/auth/reset/confirm", "/api/auth/password",
                 "/api/auth/apple/callback"):
        assert c.post(path, json={}).status_code in (404, 405), path
    assert c.get("/api/auth/apple/start", follow_redirects=False).status_code in (404, 405, 422)


def test_session_cookie_is_httponly_and_logout_really_ends_it():
    c = new_user()
    cookie = c.cookies.get("nivaaran_session")
    assert cookie and c.get("/api/auth/me").status_code == 200
    # a copy of the cookie stops working once the session is ended on the server
    thief = TestClient(app); thief.cookies.set("nivaaran_session", cookie)
    assert thief.get("/api/auth/me").status_code == 200
    assert c.post("/api/auth/logout").status_code == 200
    assert thief.get("/api/auth/me").status_code == 401 and c.get("/api/auth/me").status_code == 401
    r = TestClient(app).post("/api/demo/user")
    assert "httponly" in r.headers["set-cookie"].lower() and "samesite=lax" in r.headers["set-cookie"].lower()


def test_expired_session_is_rejected_and_removed():
    c = new_user()
    import hashlib
    token_hash = hashlib.sha256(c.cookies.get("nivaaran_session").encode()).hexdigest()
    store.execute("UPDATE sessions SET expires='2000-01-01T00:00:00+00:00' WHERE token_hash=?", (token_hash,))
    r = c.get("/api/auth/me")
    assert r.status_code == 401 and "sign in again" in _msg(r).lower()
    assert store.query("SELECT count(*) FROM sessions WHERE token_hash=?", (token_hash,))[0][0] == 0


def test_profile_updates_persist_and_missing_values_stay_empty():
    c = new_user("Meera Iyer")
    me = c.get("/api/auth/me").json()["user"]
    assert me["email"] is None and me["phone"] is None and me["avatar_url"] is None   # nothing invented
    assert c.patch("/api/auth/me", json={"name": "Meera"}).json()["user"]["name"] == "Meera"
    assert c.get("/api/auth/me").json()["user"]["name"] == "Meera"           # persisted, not just echoed
    assert c.patch("/api/auth/me", json={"name": "   "}).json()["user"]["name"] is None
    assert c.patch("/api/auth/me", json={"name": "x" * 81}).status_code == 422


def test_unauthenticated_requests_are_rejected():
    c = TestClient(app)
    for path in ("/api/claims", "/api/documents", "/api/me/overview", "/api/reports", "/api/auth/me"):
        assert c.get(path).status_code == 401
    assert c.post("/api/documents", files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")}).status_code == 401


def test_requests_from_other_websites_are_blocked():
    c = new_user()
    r = c.patch("/api/auth/me", json={"name": "Evil"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert c.patch("/api/auth/me", json={"name": "Fine"}, headers={"Origin": "http://localhost:5173"}).status_code == 200


def test_a_new_account_starts_genuinely_empty():
    c = new_user()
    ov = c.get("/api/me/overview").json()
    assert c.get("/api/claims").json() == [] and c.get("/api/documents").json() == []
    assert ov["claims"] == [] and ov["reports"] == [] and ov["discrepancy_count"] == 0


@pytest.fixture(scope="module")
def two_users():
    a = new_user("Alice")
    seeded = a.post("/api/demo/load").json()
    b = new_user("Bob")
    return a, b, seeded


def test_user_cannot_access_another_users_records(two_users):
    a, b, s = two_users
    cid, pid = s["claim_id"], s["policy_id"]
    a.get(f"/api/claims/{cid}/report.pdf")
    a.post(f"/api/claims/{cid}/ask", json={"question": "What information is missing?"})
    for path in (f"/api/claims/{cid}", f"/api/claims/{cid}/fairness", f"/api/claims/{cid}/actions", f"/api/claims/{cid}/chat",
                 f"/api/claims/{cid}/scenarios", f"/api/claims/{cid}/report.pdf", f"/api/claims/{cid}/report.json",
                 f"/api/documents/{pid}", f"/api/documents/{pid}/download", f"/api/documents/{pid}/pages/1.png",
                 f"/api/policies/{pid}/versions", f"/api/documents/{pid}/summary"):
        assert b.get(path).status_code == 404, path
    assert b.post(f"/api/claims/{cid}/ask", json={"question": "x"}).status_code == 404
    assert b.patch(f"/api/claims/{cid}", json={"cause": "x", "admission_date": "2025-09-01"}).status_code == 404
    assert b.delete(f"/api/documents/{pid}").status_code == 404
    assert b.delete(f"/api/claims/{cid}").status_code == 404
    assert b.post("/api/claims", json={"policy_document_id": pid, "admission_date": "2025-12-01",
                                       "items": [{"description": "ICU", "amount": "100"}]}).status_code == 404
    assert b.get("/api/claims").json() == [] and b.get("/api/documents").json() == []
    # ...and A's record is untouched by B's attempts
    assert a.get(f"/api/claims/{cid}").status_code == 200


def test_saved_work_persists_and_reopens(two_users):
    a, _, s = two_users
    cid = s["claim_id"]
    sc = a.post(f"/api/claims/{cid}/scenarios", json={"name": "No co-pay", "hypotheticals": {"copay_percent": "0"}}).json()
    assert sc["payable"][0] == "104600.00" and sc["base_payable"][0] == "99370.00"
    assert a.get(f"/api/claims/{cid}").json()["analysis"]["summary"]["payable_low"] == "99370.00"
    a.post(f"/api/claims/{cid}/ask", json={"question": "Why was the room charge reduced?"})
    ov = a.get("/api/me/overview").json()
    assert any(c["claim_id"] == cid for c in ov["claims"]) and ov["discrepancy_count"] >= 3 and ov["reports"]
    assert [x["name"] for x in a.get(f"/api/claims/{cid}/scenarios").json()] == ["No co-pay"]
    assert any("room" in m["question"].lower() for m in a.get(f"/api/claims/{cid}/chat").json())
    # a second session for the same account (another device) sees the same records
    other_device = TestClient(app); other_device.cookies.set("nivaaran_session", a.cookies.get("nivaaran_session"))
    assert [c["claim_id"] for c in other_device.get("/api/claims").json()] == [c["claim_id"] for c in a.get("/api/claims").json()]


def test_deleted_records_are_gone_everywhere():
    c = new_user()
    s = c.post("/api/demo/load").json()
    assert c.delete(f"/api/claims/{s['claim_id']}").status_code == 200
    assert c.get(f"/api/claims/{s['claim_id']}").status_code == 404
    assert all(x["claim_id"] != s["claim_id"] for x in c.get("/api/me/overview").json()["claims"])


def test_delete_account_removes_data_and_session():
    c = new_user()
    s = c.post("/api/demo/load").json()
    uid = c.get("/api/auth/me").json()["user"]["id"]
    assert c.delete("/api/auth/me").status_code == 200
    assert c.get("/api/auth/me").status_code == 401
    assert store.get_claim(s["claim_id"]) is None and not store.query("SELECT 1 FROM users WHERE id=?", (uid,))


def test_operator_login_link_is_single_use_and_expires():
    from app import auth
    c = new_user("Operator Target")
    uid = c.get("/api/auth/me").json()["user"]["id"]
    token = auth.create_login_link(uid)
    fresh = TestClient(app)
    r = fresh.get("/api/auth/login-link", params={"token": token}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/dashboard"
    assert fresh.get("/api/auth/me").json()["user"]["id"] == uid
    again = TestClient(app).get("/api/auth/login-link", params={"token": token}, follow_redirects=False)
    assert again.headers["location"].startswith("/login?error=")
    old = auth.create_login_link(uid, minutes=-1)
    assert TestClient(app).get("/api/auth/login-link", params={"token": old}, follow_redirects=False).headers["location"].startswith("/login?error=")


def test_ai_answers_are_labelled_and_broken_down(two_users):
    a, _, s = two_users
    r = a.post(f"/api/claims/{s['claim_id']}/ask", json={"question": "Explain this", "context": {"item_id": "L09"}}).json()
    assert r["engine"].startswith("Deterministic evidence engine")
    assert set(r["breakdown"]) == {"source_facts", "calculated", "interpretation", "assumptions", "missing"}
    assert r["breakdown"]["missing"]


def test_image_upload_without_ocr_fails_honestly(two_users):
    import pymupdf
    from app.ingestion.extract import tesseract_available
    if tesseract_available():
        pytest.skip("OCR installed")
    a, _, _ = two_users
    doc = pymupdf.open(); page = doc.new_page(); page.draw_rect(pymupdf.Rect(20, 20, 200, 200), fill=(0.3, 0.3, 0.3))
    png = page.get_pixmap().tobytes("png")
    r = a.post("/api/documents", files={"file": ("scan.png", png, "image/png")}, data={"doc_type": "policy"})
    assert r.status_code == 422 and "scanned text" in _msg(r)
    time.sleep(0)


def test_env_file_fills_only_missing_settings(tmp_path, monkeypatch):
    from app import env
    f = tmp_path / ".env"
    f.write_text("# comment\nNIVAARAN_X_A=from-file\nNIVAARAN_X_B=\"quoted\"  # note\nNIVAARAN_X_C=\n", encoding="utf-8")
    monkeypatch.setenv("NIVAARAN_X_A", "from-shell"); monkeypatch.delenv("NIVAARAN_X_B", raising=False)
    monkeypatch.delenv("NIVAARAN_NO_DOTENV")
    assert env.load(f) == ["NIVAARAN_X_B"]
    import os
    assert os.environ["NIVAARAN_X_A"] == "from-shell" and os.environ["NIVAARAN_X_B"] == "quoted" and "NIVAARAN_X_C" not in os.environ
    monkeypatch.delenv("NIVAARAN_X_B")
    monkeypatch.setenv("NIVAARAN_NO_DOTENV", "1")
    assert env.load(f) == []
