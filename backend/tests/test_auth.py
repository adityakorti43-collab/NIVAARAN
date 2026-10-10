"""Accounts, sessions, password reset, persistence, and user-to-user isolation."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth import OUTBOX
from app.main import app

PW = "correct-horse-42"


def new_user(name="Tester"):
    c = TestClient(app)
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    r = c.post("/api/auth/register", json={"email": email, "name": name, "password": PW})
    assert r.status_code == 200, r.text
    return c, email


def test_register_login_logout_and_session_persistence():
    c, email = new_user()
    assert c.get("/api/auth/me").json()["user"]["email"] == email
    cookie = c.cookies.get("nivaaran_session")
    assert cookie and "HttpOnly" in c.post("/api/auth/login", json={"email": email, "password": PW}).headers["set-cookie"]
    # a fresh client carrying the same cookie is still signed in (session persists across reloads)
    c2 = TestClient(app)
    c2.cookies.set("nivaaran_session", cookie)
    assert c2.get("/api/auth/me").status_code == 200
    c.post("/api/auth/logout")
    assert c.get("/api/auth/me").status_code == 401


def test_validation_and_wrong_password():
    c = TestClient(app)
    assert c.post("/api/auth/register", json={"email": "bad", "name": "X", "password": PW}).status_code == 400
    assert c.post("/api/auth/register", json={"email": "weak@example.com", "name": "X", "password": "short"}).status_code == 400
    _, email = new_user()
    assert c.post("/api/auth/register", json={"email": email, "name": "Y", "password": PW}).status_code == 409
    assert c.post("/api/auth/login", json={"email": email, "password": "wrong-password-1"}).status_code == 401


def test_failed_logins_are_rate_limited():
    _, email = new_user()
    c = TestClient(app)
    codes = [c.post("/api/auth/login", json={"email": email, "password": "nope-nope-1"}).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_password_never_stored_in_plaintext():
    from app import store
    _, email = new_user()
    pw_hash = store.query("SELECT pw_hash FROM users WHERE email=?", (email,))[0][0]
    assert PW not in pw_hash and pw_hash.startswith("scrypt$")


def test_password_reset_flow_via_outbox():
    c, email = new_user()
    before = set(OUTBOX.glob("*.txt")) if OUTBOX.exists() else set()
    r = TestClient(app).post("/api/auth/reset/request", json={"email": email})
    assert r.status_code == 200
    assert TestClient(app).post("/api/auth/reset/request", json={"email": "nobody@example.com"}).json() == r.json()  # no account enumeration
    mail = (set(OUTBOX.glob("*.txt")) - before).pop().read_text(encoding="utf-8")
    token = mail.split("token=")[1].split()[0]
    assert TestClient(app).post("/api/auth/reset/confirm", json={"token": token, "new_password": "brand-new-pass-7"}).status_code == 200
    assert c.get("/api/auth/me").status_code == 401  # all sessions revoked
    assert TestClient(app).post("/api/auth/reset/confirm", json={"token": token, "new_password": "another-pass-8"}).status_code == 400
    assert TestClient(app).post("/api/auth/login", json={"email": email, "password": "brand-new-pass-7"}).status_code == 200


def test_unauthenticated_requests_are_rejected():
    c = TestClient(app)
    for path in ("/api/claims", "/api/documents", "/api/me/overview", "/api/reports"):
        assert c.get(path).status_code == 401


@pytest.fixture(scope="module")
def two_users():
    a, _ = new_user("Alice")
    seeded = a.post("/api/demo/load").json()
    b, _ = new_user("Bob")
    return a, b, seeded


def test_user_cannot_access_another_users_records(two_users):
    a, b, s = two_users
    cid, pid = s["claim_id"], s["policy_id"]
    a.get(f"/api/claims/{cid}/report.pdf")
    a.post(f"/api/claims/{cid}/ask", json={"question": "What information is missing?"})
    for path in (f"/api/claims/{cid}", f"/api/claims/{cid}/fairness", f"/api/claims/{cid}/actions", f"/api/claims/{cid}/chat",
                 f"/api/claims/{cid}/scenarios", f"/api/claims/{cid}/report.pdf", f"/api/claims/{cid}/report.json",
                 f"/api/documents/{pid}", f"/api/documents/{pid}/download", f"/api/documents/{pid}/pages/1.png",
                 f"/api/policies/{pid}/versions"):
        assert b.get(path).status_code == 404, path
    assert b.post(f"/api/claims/{cid}/ask", json={"question": "x"}).status_code == 404
    assert b.patch(f"/api/claims/{cid}", json={"cause": "x", "admission_date": "2025-09-01"}).status_code == 404
    assert b.delete(f"/api/documents/{pid}").status_code == 404
    assert b.post("/api/claims", json={"policy_document_id": pid, "admission_date": "2025-12-01",
                                       "items": [{"description": "ICU", "amount": "100"}]}).status_code == 404
    assert b.get("/api/claims").json() == [] and b.get("/api/documents").json() == []


def test_saved_work_persists_and_reopens(two_users):
    a, _, s = two_users
    cid = s["claim_id"]
    sc = a.post(f"/api/claims/{cid}/scenarios", json={"name": "No co-pay", "hypotheticals": {"copay_percent": "0"}}).json()
    assert sc["payable"][0] == "104600.00" and sc["base_payable"][0] == "99370.00"
    # the saved analysis is not overwritten by the scenario
    assert a.get(f"/api/claims/{cid}").json()["analysis"]["summary"]["payable_low"] == "99370.00"
    a.post(f"/api/claims/{cid}/ask", json={"question": "Why was the room charge reduced?"})
    ov = a.get("/api/me/overview").json()
    assert any(c["claim_id"] == cid for c in ov["claims"]) and ov["discrepancy_count"] >= 3 and ov["reports"]
    assert [x["name"] for x in a.get(f"/api/claims/{cid}/scenarios").json()] == ["No co-pay"]
    assert any("room" in m["question"].lower() for m in a.get(f"/api/claims/{cid}/chat").json())


def test_delete_account_removes_data():
    c, email = new_user()
    s = c.post("/api/demo/load").json()
    assert c.delete("/api/auth/me").status_code == 200
    c2 = TestClient(app)
    assert c2.post("/api/auth/login", json={"email": email, "password": PW}).status_code == 401
    from app import store
    assert store.get_claim(s["claim_id"]) is None


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
    assert r.status_code == 422 and "OCR" in r.json()["message"]
