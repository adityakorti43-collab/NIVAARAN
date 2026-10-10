"""Integration tests: the full demo workflow through the HTTP API."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def session():
    c = TestClient(app)
    r = c.post("/api/demo/enter")  # isolated, signed-in demo workspace
    assert r.status_code == 200, r.text
    return c, r.json()


@pytest.fixture(scope="module")
def client(session):
    return session[0]


@pytest.fixture(scope="module")
def demo(session):
    return session[1]


def test_health(client):
    assert client.get("/api/health").json()["product"] == "Nivaaran"


def test_demo_before_after_comparison(demo):
    assert demo["before"]["payable_low"] == "86490.00" and demo["after"]["payable_low"] == "99370.00"
    cmp = demo["comparison"]
    assert cmp["cause"] == "Endorsement E-01 added"
    assert cmp["previous_version"] == "Base policy wording" and cmp["updated_version"] == "Policy + E-01"
    assert any("2.2 is replaced by E1.1" in r for r in cmp["reasons"])
    changed = {c["description"]: c for c in cmp["changed_items"]}
    assert "status potentially excluded -> potentially covered" in changed["Disposable gloves, masks & syringes"]["reason"]
    assert cmp["payable_delta"] == "12880.00"


def test_claim_ledger_has_evidence_with_pages(client, demo):
    a = client.get(f"/api/claims/{demo['claim_id']}").json()["analysis"]
    row = next(r for r in a["rows"] if r["original_description"] == "TV & telephone charges")
    ev = next(e for e in row["evidence"] if e["clause_id"] in row["supporting_clause_ids"])
    assert ev["section"] == "4.3" and ev["page"] == 3 and "Television" in ev["excerpt"]
    assert all(i["passed"] for i in a["invariants"])


def test_scenario_does_not_persist_and_is_labelled(client, demo):
    cid = demo["claim_id"]
    before = len(client.get(f"/api/claims/{cid}").json()["history"])
    r = client.post(f"/api/claims/{cid}/scenario", json={"copay_percent": "0"}).json()
    assert r["analysis"]["hypothetical"] is True and r["analysis"]["summary"]["payable_low"] == "104600.00"
    assert r["comparison"]["payable_delta"] == "5230.00"
    assert len(client.get(f"/api/claims/{cid}").json()["history"]) == before


def test_fact_update_creates_explained_change(client, demo):
    cid = demo["claim_id"]
    claim = client.get(f"/api/claims/{cid}").json()["claim"]
    facts = claim["facts"] | {"vitamin_prescription": "yes"}
    r = client.patch(f"/api/claims/{cid}", json={"facts": facts}).json()
    assert "vitamin prescription" in r["comparison"]["cause"]
    item = next(c for c in r["comparison"]["changed_items"] if c["description"] == "MVI Infusion")
    assert "conditional -> potentially covered" in item["reason"]


def test_compare_versions(client, demo):
    r = client.post(f"/api/claims/{demo['claim_id']}/compare-versions").json()
    labels = [v["version"]["label"] for v in r["versions"]]
    assert labels == ["Base policy wording", "Policy + E-01"]
    assert [v["is_applicable"] for v in r["versions"]] == [False, True]


@pytest.mark.parametrize("q,kind", [
    ("Which policy version applies to my treatment date?", "version"),
    ("How was the estimated payable amount calculated?", "calculation"),
    ("What information is missing?", "missing"),
    ("Why was the room charge reduced?", "item"),
    ("What changes if the nebulizer kit is removed?", "what_if"),
    ("What does the waiting period clause mean?", "clause"),
    ("Is dental scaling covered?", "coverage"),
])
def test_assistant_routes_and_grounds(client, demo, q, kind):
    r = client.post(f"/api/claims/{demo['claim_id']}/ask", json={"question": q}).json()
    assert r["kind"] == kind, r
    assert "cannot guarantee" in r["disclaimer"]


def test_assistant_admits_missing_evidence(client, demo):
    r = client.post(f"/api/claims/{demo['claim_id']}/ask", json={"question": "Is dental scaling covered?"}).json()
    assert r["grounded"] is False and "not established" in r["answer"]


def test_reports(client, demo):
    pdf = client.get(f"/api/claims/{demo['claim_id']}/report.pdf")
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
    js = client.get(f"/api/claims/{demo['claim_id']}/report.json").json()
    assert js["synthetic"] is True and js["analysis"]["rows"]


def test_upload_rejects_non_pdf(client):
    r = client.post("/api/documents", files={"file": ("policy.pdf", b"not a pdf", "application/pdf")}, data={"doc_type": "policy"})
    assert r.status_code == 422 and r.json()["error"] == "unsupported_type"


def test_reloading_demo_does_not_duplicate_documents(client, demo):
    again = client.post("/api/demo/load").json()
    assert again["endorsement_id"] == demo["endorsement_id"] and again["policy_id"] == demo["policy_id"]
    ends = [d for d in client.get("/api/documents").json() if d["doc_type"] == "endorsement"]
    assert len(ends) == 1
    assert client.get(f"/api/policies/{demo['policy_id']}/versions").json()["conflicts"] == []


def test_page_preview_renders_source_with_highlight(client, demo):
    r = client.get(f"/api/documents/{demo['policy_id']}/pages/3.png", params={"highlight": f"{demo['policy_id']}:4.3"})
    assert r.status_code == 200 and r.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert client.get(f"/api/documents/{demo['policy_id']}/pages/99.png").status_code == 404


def test_document_in_use_cannot_be_deleted(client, demo):
    assert client.delete(f"/api/documents/{demo['policy_id']}").status_code == 409


def test_document_listing_hides_internal_paths(client, demo):
    text = client.get("/api/documents").text
    assert "uploads" not in text and ":\\" not in text


def test_manual_claim_entry(client, demo):
    body = {"title": "Manual", "policy_document_id": demo["policy_id"], "endorsement_ids": [demo["endorsement_id"]],
            "admission_date": "2025-12-01", "discharge_date": "2025-12-02", "diagnosis": "Observation",
            "items": [{"description": "ICU charges", "amount": "15000", "quantity": "1"}]}
    r = client.post("/api/claims", json=body)
    assert r.status_code == 200
    row = r.json()["analysis"]["rows"][0]
    assert row["eligible_amount"] == "10000.00" and row["status"] == "partially_payable"


def test_cost_estimate_is_labelled_hypothetical(client, demo):
    ds = client.get("/api/costs").json()
    assert ds["dataset"]["data_type"] == "illustrative_synthetic"
    r = client.post("/api/costs/estimate", json={"procedure": "lap_appendicectomy", "claim_id": demo["claim_id"]}).json()
    assert "HYPOTHETICAL" in r["label"] and r["analysis"]["summary"]["total_billed"] == "125000.00"


def test_invalid_claim_input(client, demo):
    r = client.post("/api/claims", json={"policy_document_id": demo["policy_id"], "admission_date": "2025-12-01"})
    assert r.status_code == 400
