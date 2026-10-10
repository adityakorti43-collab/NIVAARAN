"""Sign-in with a phone code, Google and Apple; and the whole-policy read-aloud summaries (English, Hindi, Marathi)."""
import base64
import json
import time

import pytest
from fastapi.testclient import TestClient

from app import social, store
from app.main import app


def _client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def demo():
    c = TestClient(app)
    return c, c.post("/api/demo/enter").json()


def _id_token(claims: dict) -> str:
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")  # noqa: E731
    return f"{enc({'alg': 'RS256'})}.{enc(claims)}.signature"


class _Resp:
    def __init__(self, status: int, body: dict):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


# ------------------------------------------------------------------------------------------------- phone codes
def test_phone_code_signs_in_and_reuses_the_account(monkeypatch):
    monkeypatch.setattr(social, "DEV_OTP", True)
    social._sent.clear()
    c = _client()
    start = c.post("/api/auth/phone/start", json={"phone": "98200 12345"}).json()
    assert start["phone"] == "+919820012345" and start["delivery"] == "outbox" and len(start["dev_code"]) == 6
    assert c.post("/api/auth/phone/verify", json={"phone": "9820012345", "code": "999999" if start["dev_code"] != "999999" else "111111"}).status_code == 401
    ok = c.post("/api/auth/phone/verify", json={"phone": "+91 98200 12345", "code": start["dev_code"], "name": "Meera"})
    assert ok.status_code == 200
    u = ok.json()["user"]
    assert u["phone"] == "+919820012345" and u["provider"] == "phone" and u["name"] == "Meera" and u["has_password"] is False
    assert c.get("/api/auth/me").json()["user"]["id"] == u["id"]
    # the code is single use
    assert c.post("/api/auth/phone/verify", json={"phone": "9820012345", "code": start["dev_code"]}).status_code == 400
    # signing in again with the same number reaches the same account
    social._sent.clear()
    again = c.post("/api/auth/phone/start", json={"phone": "9820012345"}).json()
    u2 = c.post("/api/auth/phone/verify", json={"phone": "9820012345", "code": again["dev_code"]}).json()["user"]
    assert u2["id"] == u["id"]


def test_phone_codes_are_rate_limited_and_attempts_capped(monkeypatch):
    monkeypatch.setattr(social, "DEV_OTP", False)
    social._sent.clear()
    c = _client()
    first = c.post("/api/auth/phone/start", json={"phone": "9811100000"}).json()
    assert "dev_code" not in first                      # never exposed unless explicitly enabled for local testing
    assert c.post("/api/auth/phone/start", json={"phone": "9811100000"}).status_code == 429
    for _ in range(5):
        assert c.post("/api/auth/phone/verify", json={"phone": "9811100000", "code": "123456"}).status_code in (401, 429)
    assert c.post("/api/auth/phone/verify", json={"phone": "9811100000", "code": "123456"}).status_code in (400, 429)
    assert c.post("/api/auth/phone/start", json={"phone": "12"}).status_code == 400


def test_code_is_stored_only_as_a_hash(monkeypatch):
    monkeypatch.setattr(social, "DEV_OTP", True)
    social._sent.clear()
    code = _client().post("/api/auth/phone/start", json={"phone": "9822233344"}).json()["dev_code"]
    stored = store.query("SELECT code_hash FROM otp_codes WHERE phone=?", ("+919822233344",))[0][0]
    assert code not in stored and len(stored) == 64


# ------------------------------------------------------------------------------------------------ Google / Apple
def test_providers_report_honestly_when_not_configured(monkeypatch):
    monkeypatch.setattr(social, "GOOGLE_ID", ""); monkeypatch.setattr(social, "APPLE_ID", "")
    c = _client()
    p = c.get("/api/auth/providers").json()
    assert p["google"] is False and p["apple"] is False and p["phone"]["enabled"] is True
    r = c.get("/api/auth/google/start", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login?error=")


@pytest.fixture
def google(monkeypatch):
    monkeypatch.setattr(social, "GOOGLE_ID", "client-123.apps.googleusercontent.com")
    monkeypatch.setattr(social, "GOOGLE_SECRET", "secret")
    claims = {"iss": "https://accounts.google.com", "aud": "client-123.apps.googleusercontent.com", "exp": time.time() + 600,
              "sub": "g-1001", "email": "asha.k@example.com", "email_verified": True, "name": "Asha K"}
    monkeypatch.setattr(social.httpx, "post", lambda *a, **k: _Resp(200, {"id_token": _id_token(claims)}))
    return claims


def _start_state(c: TestClient, provider: str, next_: str = "/claim") -> str:
    loc = c.get(f"/api/auth/{provider}/start", params={"next": next_}, follow_redirects=False).headers["location"]
    from urllib.parse import parse_qs, urlparse
    q = parse_qs(urlparse(loc).query)
    assert q["redirect_uri"][0].endswith(f"/api/auth/{provider}/callback")
    return q["state"][0]


def test_google_sign_in_creates_account_and_session(google):
    c = _client()
    state = _start_state(c, "google", "/claim")
    r = c.get("/api/auth/google/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/claim"
    me = c.get("/api/auth/me").json()["user"]
    assert me["email"] == "asha.k@example.com" and me["provider"] == "google" and me["has_password"] is False
    # the state is single use
    assert c.get("/api/auth/google/callback", params={"code": "abc", "state": state}, follow_redirects=False).headers["location"].startswith("/login?error=")


def test_google_links_to_existing_account_with_same_verified_email(google, monkeypatch):
    c = _client()
    c.post("/api/auth/register", json={"email": "linked.user@example.com", "name": "Linked", "password": "correct horse 42"})
    uid = c.get("/api/auth/me").json()["user"]["id"]
    google.update(sub="g-2002", email="linked.user@example.com")
    monkeypatch.setattr(social.httpx, "post", lambda *a, **k: _Resp(200, {"id_token": _id_token(google)}))
    c2 = _client()
    state = _start_state(c2, "google")
    c2.get("/api/auth/google/callback", params={"code": "x", "state": state}, follow_redirects=False)
    assert c2.get("/api/auth/me").json()["user"]["id"] == uid


@pytest.mark.parametrize("bad", [{"aud": "someone-else"}, {"iss": "https://evil.example"}, {"exp": time.time() - 10}])
def test_google_rejects_tokens_for_other_audiences_issuers_or_expired(google, monkeypatch, bad):
    monkeypatch.setattr(social.httpx, "post", lambda *a, **k: _Resp(200, {"id_token": _id_token({**google, **bad})}))
    c = _client()
    state = _start_state(c, "google")
    r = c.get("/api/auth/google/callback", params={"code": "x", "state": state}, follow_redirects=False)
    assert r.headers["location"].startswith("/login?error=") and c.get("/api/auth/me").status_code == 401


def test_forged_state_and_open_redirects_are_refused(google):
    c = _client()
    r = c.get("/api/auth/google/callback", params={"code": "x", "state": "made-up"}, follow_redirects=False)
    assert r.headers["location"].startswith("/login?error=")
    state = _start_state(c, "google", "https://evil.example/steal")
    r = c.get("/api/auth/google/callback", params={"code": "x", "state": state}, follow_redirects=False)
    assert r.headers["location"] == "/dashboard"


def test_apple_form_post_callback_uses_first_sign_in_name(monkeypatch):
    monkeypatch.setattr(social, "APPLE_ID", "in.nivaaran.web"); monkeypatch.setattr(social, "APPLE_SECRET", "jwt")
    claims = {"iss": "https://appleid.apple.com", "aud": "in.nivaaran.web", "exp": time.time() + 600, "sub": "000123.apple",
              "email": "x7@privaterelay.appleid.com", "email_verified": "true"}
    monkeypatch.setattr(social.httpx, "post", lambda *a, **k: _Resp(200, {"id_token": _id_token(claims)}))
    c = _client()
    state = _start_state(c, "apple")
    r = c.post("/api/auth/apple/callback", data={"code": "c", "state": state, "user": json.dumps({"name": {"firstName": "Ravi", "lastName": "Patil"}})},
               follow_redirects=False)
    assert r.status_code == 303
    me = c.get("/api/auth/me").json()["user"]
    assert me["name"] == "Ravi Patil" and me["provider"] == "apple"


def test_social_account_can_set_a_first_password(google):
    c = _client()
    c.get("/api/auth/google/callback", params={"code": "x", "state": _start_state(c, "google")}, follow_redirects=False)
    assert c.post("/api/auth/password", json={"current_password": "", "new_password": "a new pass 123"}).json()["changed"]
    assert c.get("/api/auth/me").json()["user"]["has_password"] is True


# ------------------------------------------------------------------------------------- policy read-aloud summaries
def test_policy_summary_in_english_hindi_and_marathi(demo):
    c, d = demo
    out = {lang: c.get(f"/api/documents/{d['policy_id']}/summary", params={"lang": lang}).json() for lang in ("en", "hi", "mr")}
    assert [s["heading"] for s in out["en"]["sections"]][0] == "What is covered"
    assert out["hi"]["sections"][0]["heading"] == "क्या कवर है" and "धारा" in out["hi"]["text"]
    assert out["mr"]["sections"][0]["heading"] == "काय कव्हर आहे" and "कलम" in out["mr"]["text"]
    # every point cites a clause that exists in the document, and amounts come from the clauses themselves
    doc = c.get(f"/api/documents/{d['policy_id']}").json()
    sections = {cl["section"] for cl in doc["clauses"]}
    for lang in out:
        for s in out[lang]["sections"]:
            assert all(i["clause"] in sections for i in s["items"])
    assert "10,000.00" in out["mr"]["text"]   # the deductible / ICU limits, rendered from the policy
    mr = c.get(f"/api/documents/{d['policy_id']}/clauses/5.1/explain", params={"lang": "mr"}).json()["text"]
    assert "कलम 5.1" in mr and "10,000.00" in mr


# ------------------------------------------------------------------------------------- questions in Hindi / Marathi
@pytest.mark.parametrize("q,lang,expect", [
    ("क्या मेरे कमरे का पूरा किराया मिलेगा?", "hi", "Deluxe Room Charges"),
    ("माझ्या खोलीचे पूर्ण भाडे मिळेल का?", "mr", "Deluxe Room Charges"),
    ("आईसीयू का खर्च कवर है?", "hi", "ICU Charges"),
    ("रुग्णवाहिकेचे पैसे किती मिळतील?", "mr", "Ambulance"),
    ("विटामिन ड्रिप के पैसे क्यों काटे?", "hi", "4.2"),
    ("माझ्या खिशातून किती पैसे जातील?", "mr", "out-of-pocket share"),
])
def test_questions_in_hindi_and_marathi_are_answered_from_the_documents(demo, q, lang, expect):
    c, d = demo
    a = c.post(f"/api/claims/{d['claim_id']}/ask", json={"question": q}).json()
    assert a["language"] == lang and a["grounded"] is True and expect in a["answer"]
    assert a["answer"].startswith("आपका सवाल" if lang == "hi" else "तुमचा प्रश्न")   # says how the question was read
    assert a["question"] == q


def test_unreadable_indic_question_says_so_in_that_language(demo):
    c, d = demo
    a = c.post(f"/api/claims/{d['claim_id']}/ask", json={"question": "नमस्ते"}).json()
    assert a["grounded"] is False and "समझ नहीं आया" in a["answer"]
