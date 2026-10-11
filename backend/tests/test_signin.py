"""Sign-in: Google (OAuth code flow with PKCE), the only sign-in method.

Google's token endpoint is simulated here (httpx.post is patched) so the flows can be tested without credentials or a phone.
Those simulations exist only inside this test file; the application never falls back to them. Also covers the policy
read-aloud summaries, multilingual questions, the test pack, and automatic document typing."""
import base64
import json
import time
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app import auth, social, store
from app.main import app


def _msg(r) -> str:
    b = r.json()
    return str(b.get("message") or b.get("detail") or "")


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


def _users_with(where: str, args: tuple) -> int:
    return store.query(f"SELECT count(*) FROM users WHERE {where}", args)[0][0]


def test_concurrent_creation_of_the_same_identity_yields_one_account():
    sub = f"g-race-{time.time_ns()}"
    a = auth.insert_user({"google_sub": sub, "provider": "google"}, "google_sub=?", (sub,))
    b = auth.insert_user({"google_sub": sub, "provider": "google"}, "google_sub=?", (sub,))
    assert a.id == b.id and _users_with("google_sub=?", (sub,)) == 1


# ================================================================================ Google (token endpoint simulated)
@pytest.fixture
def google(monkeypatch):
    monkeypatch.setattr(social, "GOOGLE_ID", "client-123.apps.googleusercontent.com")
    monkeypatch.setattr(social, "GOOGLE_SECRET", "secret")
    claims = {"iss": "https://accounts.google.com", "aud": "client-123.apps.googleusercontent.com", "exp": time.time() + 600,
              "sub": f"g-{time.time_ns()}", "email": f"asha{time.time_ns()}@gmail.com", "email_verified": True, "name": "Asha K",
              "picture": "https://lh3.googleusercontent.com/a/photo"}
    sent = {}

    def post(url, data=None, **kw):
        sent.update(data or {})
        return _Resp(200, {"id_token": _id_token(claims)})
    monkeypatch.setattr(social.httpx, "post", post)
    return claims, sent


def _start(c: TestClient, next_: str = "/claim", link: bool = False) -> dict:
    r = c.get("/api/auth/google/start", params={"next": next_} | ({"link": 1} if link else {}), follow_redirects=False)
    assert r.status_code == 303
    loc = urlparse(r.headers["location"])
    assert loc.netloc == "accounts.google.com", r.headers["location"]
    return {k: v[0] for k, v in parse_qs(loc.query).items()}


def test_google_start_uses_pkce_and_a_single_use_state(google):
    q = _start(_client())
    assert q["code_challenge_method"] == "S256" and len(q["code_challenge"]) >= 43 and q["scope"] == "openid email profile"
    assert q["redirect_uri"].endswith("/api/auth/google/callback") and q["state"]


def test_google_sign_in_creates_then_reuses_the_account(google):
    claims, sent = google
    c = _client()
    q = _start(c)
    r = c.get("/api/auth/google/callback", params={"code": "abc", "state": q["state"]}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/claim" and sent["code_verifier"]   # PKCE verifier sent to Google
    me = c.get("/api/auth/me").json()["user"]
    assert me["provider"] == "google" and me["email"] == claims["email"] and me["email_verified"] and me["avatar_url"] and me["google_linked"]
    c2 = _client()
    c2.get("/api/auth/google/callback", params={"code": "abc", "state": _start(c2)["state"]}, follow_redirects=False)
    assert c2.get("/api/auth/me").json()["user"]["id"] == me["id"] and _users_with("google_sub=?", (claims["sub"],)) == 1
    # the state is single use
    assert c.get("/api/auth/google/callback", params={"code": "abc", "state": q["state"]}, follow_redirects=False).headers["location"].startswith("/login?error=")


def test_google_does_not_merge_into_an_account_with_the_same_email(google):
    claims, _ = google
    victim = auth.insert_user({"email": claims["email"], "name": "Someone else", "provider": "password"}, "email=?", (claims["email"],))
    c = _client()
    c.get("/api/auth/google/callback", params={"code": "x", "state": _start(c)["state"]}, follow_redirects=False)
    me = c.get("/api/auth/me").json()["user"]
    assert me["id"] != victim.id and me["email"] is None          # separate account; no takeover, no duplicate address
    assert auth.get_user("id=?", (victim.id,)).google_linked is False


def test_google_can_be_linked_from_a_signed_in_account(google):
    claims, _ = google
    c = _client(); c.post("/api/demo/user", params={"name": "Linker"})
    uid = c.get("/api/auth/me").json()["user"]["id"]
    r = c.get("/api/auth/google/callback", params={"code": "x", "state": _start(c, link=True)["state"]}, follow_redirects=False)
    assert r.headers["location"] == "/settings?linked=google"
    me = c.get("/api/auth/me").json()["user"]
    assert me["id"] == uid and me["google_linked"] and me["name"] == "Linker"      # existing profile preserved
    other = _client(); other.post("/api/demo/user", params={"name": "Other"})
    r = other.get("/api/auth/google/callback", params={"code": "x", "state": _start(other, link=True)["state"]}, follow_redirects=False)
    assert "already+linked" in r.headers["location"]


@pytest.mark.parametrize("bad", [{"aud": "someone-else"}, {"iss": "https://evil.example"}, {"exp": time.time() - 10}, {"sub": ""}])
def test_google_rejects_unverifiable_tokens(google, monkeypatch, bad):
    claims, _ = google
    monkeypatch.setattr(social.httpx, "post", lambda *a, **k: _Resp(200, {"id_token": _id_token({**claims, **bad})}))
    c = _client()
    r = c.get("/api/auth/google/callback", params={"code": "x", "state": _start(c)["state"]}, follow_redirects=False)
    assert r.headers["location"].startswith("/login?error=") and c.get("/api/auth/me").status_code == 401


def test_google_cancel_misconfiguration_and_forgery_are_handled(google, monkeypatch):
    c = _client()
    r = c.get("/api/auth/google/callback", params={"error": "access_denied"}, follow_redirects=False)
    assert "cancelled" in r.headers["location"] and c.get("/api/auth/me").status_code == 401
    r = c.get("/api/auth/google/callback", params={"code": "x", "state": "made-up"}, follow_redirects=False)
    assert r.headers["location"].startswith("/login?error=")
    state = _start(c, "https://evil.example/steal")["state"]
    assert c.get("/api/auth/google/callback", params={"code": "x", "state": state}, follow_redirects=False).headers["location"] == "/dashboard"
    monkeypatch.setattr(social.httpx, "post", lambda *a, **k: _Resp(401, {"error": "invalid_client"}))
    r = c.get("/api/auth/google/callback", params={"code": "x", "state": _start(c)["state"]}, follow_redirects=False)
    assert "misconfigured" in r.headers["location"]
    monkeypatch.setattr(social, "GOOGLE_ID", "")
    r = c.get("/api/auth/google/start", follow_redirects=False)
    assert r.headers["location"].startswith("/login?error=") and "set+up" in r.headers["location"]


def test_phone_sign_in_and_unlinking_are_gone():
    c = _client()
    for path in ("/api/auth/phone/start", "/api/auth/phone/verify"):
        assert c.post(path, json={"phone": "9820012345", "code": "123456"}).status_code in (404, 405), path
    assert c.delete("/api/auth/identities/google").status_code in (401, 404, 405)
    assert set(c.get("/api/auth/providers").json()) == {"google"}


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
    # the quick spoken explanation is much shorter, reads no clause numbers, and stays in the chosen language
    for lang, intro in (("en", "in a nutshell"), ("hi", "आसान भाषा में"), ("mr", "थोडक्यात")):
        q = out[lang]["quick_text"]
        assert intro in q and len(q) < len(out[lang]["text"]) * 0.7 and "(clause" not in q and "(धारा" not in q and "(कलम" not in q
    # the English and Hindi explanations are conversational and say amounts the way people do
    assert "5,000 rupees a day" in out["en"]["quick_text"] and ".00" not in out["en"]["quick_text"]
    assert "first 10,000 rupees each year" in out["en"]["quick_text"] and "10 percent" in out["en"]["quick_text"]
    assert "24 months" in out["en"]["quick_text"] and "won't pay for" in out["en"]["quick_text"]
    assert "10,000 रुपये" in out["hi"]["quick_text"] and ".00" not in out["hi"]["quick_text"]
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


# ------------------------------------------------------------------------- the Arogya Kavach test pack, end to end
def test_arogya_kavach_test_pack_matches_its_design(tmp_path):
    """Every bill line in demo/test_pack.py is designed to trigger one rule; check the engine's decision for each."""
    from demo import test_pack as P
    paths = P.generate(tmp_path)
    c = TestClient(app)
    c.post("/api/demo/user")
    up = lambda k, t: c.post("/api/documents", files={"file": (paths[k].name, paths[k].read_bytes(), "application/pdf")}, data={"doc_type": t}).json()
    pol, a01, a02 = up("policy", "policy"), up("endorsement", "endorsement"), up("future", "endorsement")
    bill = c.post("/api/bills/parse", files={"file": ("bill.pdf", paths["bill"].read_bytes(), "application/pdf")}).json()
    bill = bill.get("bill", bill)
    a = c.post("/api/claims", json={"policy_document_id": pol["document_id"], "endorsement_ids": [a01["document_id"], a02["document_id"]],
                                    "bill": bill, "admission_date": "2026-03-10", "discharge_date": "2026-03-14"}).json()["analysis"]
    assert a["version"]["selected"]["label"] == "Policy + A-01"           # A-02 is effective after admission
    rows = {r["line_no"]: r for r in a["rows"]}
    expect = {1: ("partially_payable", "10000.00"), 2: ("partially_payable", "16000.00"), 3: ("potentially_covered", "45000.00"),
              6: ("conditional", None), 8: ("potentially_covered", "4500.00"), 9: ("potentially_excluded", "0.00"),
              12: ("conditional", None), 13: ("partially_payable", "3000.00"), 14: ("potentially_excluded", "0.00"),
              15: ("potentially_excluded", "0.00"), 16: ("potentially_excluded", "0.00"), 17: ("potentially_excluded", "0.00"),
              18: ("partially_payable", "2500.00"), 19: ("partially_payable", "5000.00"), 20: ("potentially_covered", "1500.00"),
              21: ("insufficient_evidence", None), 22: ("insufficient_evidence", None)}
    for n, (status, eligible) in expect.items():
        assert rows[n]["status"] == status, (n, rows[n]["status"], rows[n]["explanation"])
        assert (rows[n]["eligible_amount"] is None and eligible is None) or rows[n]["eligible_amount"] == eligible, (n, rows[n]["eligible_amount"])
    s = a["summary"]
    assert s["payable_low"] == "153450.00"                                # (185,500 − 15,000 deductible) × 90%
    facts = {**c.get(f"/api/claims/{a['claim_id']}").json()["claim"]["facts"], "implant_invoice_submitted": "yes", "vitamin_prescription": "yes"}
    b = c.patch(f"/api/claims/{a['claim_id']}", json={"facts": facts}).json()["analysis"]
    assert b["summary"]["payable_low"] == "200000.00"                     # sum-insured cap
    cap = next(t for t in b["trace_low"] if t["stage"] == "sum_insured_cap")
    assert cap["amount_before"] == "254070.00" and cap["amount_after"] == "200000.00"


def test_upload_type_is_detected_automatically_and_an_explicit_correction_is_kept(tmp_path):
    from demo import test_pack as P
    paths = P.generate(tmp_path)
    c = TestClient(app)
    c.post("/api/demo/user")
    up = lambda k, t=None: c.post("/api/documents", files={"file": (paths[k].name, paths[k].read_bytes(), "application/pdf")},
                                  data={"doc_type": t} if t else {}).json()
    assert up("policy")["doc_type"] == "policy"
    assert up("endorsement")["doc_type"] == "endorsement"
    assert up("brochure")["doc_type"] == "benefit_summary"
    # "Wrong type? Save it as ..." re-files the same file as the chosen type, replacing the earlier copy
    r = up("brochure", "policy")
    assert r["doc_type"] == "policy" and any("as you chose" in w for w in r["warnings"])
    kinds = [d["doc_type"] for d in c.get("/api/documents").json() if d["filename"] == paths["brochure"].name]
    assert kinds == ["policy"]


def test_google_sign_in_from_the_phone_app_hands_a_single_use_link_back(google):
    claims, _ = google
    c = _client()
    r = c.get("/api/auth/google/start", params={"next": "/documents", "app": 1}, follow_redirects=False)
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    back = c.get("/api/auth/google/callback", params={"code": "x", "state": state}, follow_redirects=False)
    loc = urlparse(back.headers["location"])
    assert loc.scheme == social.APP_SCHEME and loc.netloc == "auth"
    q = {k: v[0] for k, v in parse_qs(loc.query).items()}
    assert q["next"] == "/documents" and q["token"]
    assert c.get("/api/auth/me").status_code == 401                  # no session in the system browser
    app_view = _client()                                              # the app's own web view opens the link
    r = app_view.get("/api/auth/login-link", params={"token": q["token"], "next": q["next"]}, follow_redirects=False)
    assert r.headers["location"] == "/documents" and app_view.get("/api/auth/me").json()["user"]["email"] == claims["email"]
    again = _client().get("/api/auth/login-link", params={"token": q["token"]}, follow_redirects=False)
    assert again.headers["location"].startswith("/login?error=")       # single use
