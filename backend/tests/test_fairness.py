"""Fraud & Fairness Intelligence and Action Center, run against the synthetic demo through the HTTP API."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def demo():
    c = TestClient(app)
    d = c.post("/api/demo/enter").json()
    return c, d


def test_finds_intended_brochure_discrepancies(demo):
    c, d = demo
    f = c.get(f"/api/claims/{d['claim_id']}/fairness").json()
    titles = " | ".join(x["title"] for x in f["findings"])
    assert "Room Rent: INR 10,000.00 in the summary vs INR 7,500.00 in the policy" in titles
    assert "Co-payment stated as 0% but the policy applies 5%" in titles
    assert f["status"] == "multiple_issues"
    rep = next(x for x in f["findings"] if x["id"].startswith("rep-S1.1"))
    assert rep["excerpts"][0]["section"] == "S1.1" and rep["conflicting_excerpts"][0]["section"] == "E1.1"
    assert rep["conflicting_excerpts"][0]["page"] == 1


def test_consistent_terms_are_not_flagged(demo):
    c, d = demo
    f = c.get(f"/api/claims/{d['claim_id']}/fairness").json()
    consistent = {k["check"] for k in f["checks"] if k["result"] == "consistent"}
    assert any("Road Ambulance" in k for k in consistent) and any("Deductible" in k for k in consistent)
    assert not any("Ambulance" in x["title"] or "Deductible" in x["title"] for x in f["findings"])


def test_restrictive_exclusion_is_not_called_a_discrepancy(demo):
    c, d = demo
    f = c.get(f"/api/claims/{d['claim_id']}/fairness").json()
    assert {r["item"] for r in f["restrictive_terms"]} == {"Admission kit & toiletries", "TV & telephone charges"}
    assert not any("TV" in x["title"] or "Admission kit" in x["title"] for x in f["findings"])
    assert all("probab" not in str(x).lower() for x in f["findings"])  # no invented fraud probabilities
    assert "legal determination" in " ".join(f["limitations"])


def test_action_center_letter_is_neutral_and_grounded(demo):
    c, d = demo
    a = c.get(f"/api/claims/{d['claim_id']}/actions").json()
    letter = a["letter"].lower()
    assert "nebulizer kit" in letter and "co-payment" in letter
    for word in ("fraud", "cheat", "deadline", "legal action"):
        assert word not in letter
    assert a["missing_documents"]


def test_copilot_uses_context_and_refuses_unsupported_conclusion(demo):
    c, d = demo
    r = c.post(f"/api/claims/{d['claim_id']}/ask", json={"question": "Is this evidence sufficient to conclude that I was misled?"}).json()
    assert r["kind"] == "fairness" and "do not by themselves establish" in r["answer"]
    r = c.post(f"/api/claims/{d['claim_id']}/ask", json={"question": "Explain this in simpler language", "context": {"item_id": "L09"}}).json()
    assert r["kind"] == "item" and "MVI Infusion" in r["answer"] and any(a["type"] == "open_clause" for a in r["actions"])
    r = c.post(f"/api/claims/{d['claim_id']}/ask", json={"question": "Help me draft a letter to my insurer"}).json()
    assert r["kind"] == "draft" and r["draft"].startswith("Subject: Request for clarification")


def test_clause_read_aloud_in_hindi_and_english(demo):
    c, d = demo
    hi = c.get(f"/api/documents/{d['endorsement_id']}/clauses/E1.1/explain", params={"lang": "hi"}).json()["text"]
    assert "7,500.00" in hi and "प्रति दिन" in hi and "धारा E1.1" in hi
    en = c.get(f"/api/documents/{d['policy_id']}/clauses/5.1/explain", params={"lang": "en"}).json()["text"]
    assert "10,000.00" in en and "deductible" in en.lower()
    assert c.post("/api/translate/hi", json={"text": "x"}).status_code == 409  # honest when AI isn't configured


def test_undated_endorsement_is_ambiguous_version_case(demo):
    from demo.generate_demo import OUT_DIR
    c, d = demo
    up = c.post("/api/documents", files={"file": ("e02.pdf", (OUT_DIR / "synthetic_endorsement_E02_undated.pdf").read_bytes(), "application/pdf")},
                data={"doc_type": "endorsement"}).json()
    v = c.get(f"/api/policies/{d['policy_id']}/versions", params={"endorsement_ids": f"{d['endorsement_id']},{up['document_id']}"}).json()
    assert any("no effective date" in x for x in v["conflicts"])
