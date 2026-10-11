"""Policy-only tools: estimate, ask, checklist and the summary PDF, all from the user's own policy (no claim needed)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def setup():
    c = TestClient(app)
    c.post("/api/demo/user")
    d = c.post("/api/demo/load").json()
    return c, d["policy_id"]


def test_estimate_runs_the_real_calculation_and_saves_nothing(setup):
    c, pid = setup
    before = len(c.get("/api/claims").json())
    r = c.post(f"/api/policies/{pid}/estimate", json={"admission_date": "2025-09-10", "discharge_date": "2025-09-13", "items": [
        {"description": "Room rent", "amount": "21000", "quantity": "3"},
        {"description": "Television charges", "amount": "900", "quantity": "3"}]})
    assert r.status_code == 200 and r.json()["saved"] is False
    a = r.json()["analysis"]
    rows = {x["original_description"]: x for x in a["rows"]}
    assert rows["Room rent"]["eligible_amount"] == "15000.00"           # capped at ₹5,000/day × 3 by clause 2.2
    assert rows["Television charges"]["status"] == "potentially_excluded"
    assert len(c.get("/api/claims").json()) == before                  # nothing persisted


def test_ask_answers_from_clauses_in_english_and_hindi(setup):
    c, pid = setup
    en = c.post(f"/api/policies/{pid}/ask", json={"question": "Is there a limit on room rent?"}).json()
    assert en["grounded"] and en["citations"][0]["section"] == "2.2" and "5,000" in en["answer"]
    hi = c.post(f"/api/policies/{pid}/ask", json={"question": "कमरे का किराया कितना मिलेगा?"}).json()
    assert hi["language"] == "hi" and hi["citations"] and "धारा" in hi["answer"]
    none = c.post(f"/api/policies/{pid}/ask", json={"question": "Does it cover my car insurance premium?"}).json()
    assert none["citations"]                                           # points to the nearest clause either way


def test_checklist_lists_claim_documents_and_waiting_period_dates(setup):
    c, pid = setup
    ck = c.get(f"/api/policies/{pid}/checklist").json()
    docs = " ".join(d["text"].lower() for d in ck["claim_documents"])
    assert "discharge summary" in docs and "itemised final bill" in docs
    pre = next(w for w in ck["waits"] if w["months"] == 48)
    assert pre["covered_from"] == "2026-04-01"                         # continuous cover since 2022-04-01 + 48 months
    assert ck["deductible"]["amount"] == "10000.00" and ck["copay"]["percent"] == "10"


def test_summary_pdf_downloads(setup):
    c, pid = setup
    r = c.get(f"/api/policies/{pid}/summary.pdf")
    assert r.status_code == 200 and r.content[:5] == b"%PDF-" and "attachment" in r.headers["content-disposition"]


def test_policy_tools_are_private(setup):
    _, pid = setup
    other = TestClient(app); other.post("/api/demo/user")
    assert other.get(f"/api/policies/{pid}/checklist").status_code == 404
    assert other.post(f"/api/policies/{pid}/ask", json={"question": "room rent"}).status_code == 404
