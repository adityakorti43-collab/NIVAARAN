"""Policies in formats other than "2.1 Heading" are accepted, split into citable clauses and interpreted."""
import time

import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient

from app.main import app


def _pdf(lines: list[str]) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    y = 50
    for ln in lines:
        if y > 800:
            page, y = doc.new_page(), 50
        page.insert_text((50, y), ln, fontname="helv", fontsize=10)
        y += 16
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def client():
    c = TestClient(app)
    c.post("/api/demo/user")
    return c


def _upload(c, data: bytes) -> dict:
    r = c.post("/api/documents", files={"file": ("policy.pdf", data, "application/pdf")}, data={"doc_type": "policy"})
    assert r.status_code == 200, r.text
    return c.get(f"/api/documents/{r.json()['document_id']}").json()


def _claim(c, doc_id: str, items: list[dict]) -> dict:
    r = c.post("/api/claims", json={"policy_document_id": doc_id, "items": items, "admission_date": "2026-07-10",
                                     "discharge_date": "2026-07-13", "facts": {"accident": "yes"}})
    assert r.status_code == 200, r.text
    return {row["original_description"]: row for row in r.json()["analysis"]["rows"]}


def test_bracketed_clause_ids_and_rupee_glyph(client):
    data = _pdf([
        "SAMPLE ACCIDENT HEALTH POLICY", "Policy number", "TST-BR-0001", "Policy period", "01 January 2026 to 31 December 2026",
        "Sum insured", "I5,00,000",
        "1. Key Definitions",
        "[DEF-01] Accident - A sudden, unforeseen event caused by an external force.",
        "2. Benefits and Coverage",
        "[COV-01] Surgery and diagnostics - Surgery, imaging, laboratory tests and medicines are eligible.",
        "[COV-02] Ambulance - Emergency ground ambulance charges are eligible up to I5,000 per accident.",
        "3. Limits",
        "[LIM-01] Room rent - Room rent is limited to I4,000 per day.",
        "[LIM-02] Deductible - The first I2,000 of eligible expenses for each claim is payable by the insured person.",
        "[LIM-03] Co-payment - The insured person pays 10% of the remaining eligible amount.",
        "4. Exclusions",
        "[EXC-01] Comfort items - Television charges and guest meals are excluded.",
    ])
    doc = _upload(client, data)
    by = {c["section"]: c["interpretation"] for c in doc["clauses"]}
    assert {"DEF-01", "COV-01", "COV-02", "LIM-01", "LIM-02", "LIM-03", "EXC-01"} <= set(by)
    assert by["LIM-01"]["category"] == "limit" and by["LIM-01"]["limit"]["amount"] == "4000.00"
    assert by["LIM-02"]["category"] == "deductible" and by["LIM-02"]["amount"] == "2000.00"
    assert by["LIM-03"]["category"] == "copayment" and by["LIM-03"]["percent"] == "10"
    assert by["EXC-01"]["category"] == "exclusion" and by["DEF-01"]["category"] == "definition"
    assert doc["metadata"]["sum_insured"] == "500000.00" and doc["metadata"]["policy_number"] == "TST-BR-0001"
    rows = _claim(client, doc["document_id"], [
        {"description": "Room charges", "amount": "15000", "quantity": "3", "service_date": "2026-07-10"},
        {"description": "Ambulance charges", "amount": "7000", "service_date": "2026-07-10"},
        {"description": "CT scan", "amount": "6000", "service_date": "2026-07-11"},
        {"description": "Television charges", "amount": "500", "service_date": "2026-07-11"}])
    assert rows["Room charges"]["status"] == "partially_payable" and rows["Room charges"]["eligible_amount"] == "12000.00"
    assert rows["Ambulance charges"]["eligible_amount"] == "5000.00"
    assert rows["CT scan"]["status"] == "potentially_covered"
    assert rows["Television charges"]["status"] == "potentially_excluded"


def test_clause_word_numbering(client):
    doc = _upload(client, _pdf([
        "SIMPLE HEALTH COVER", "Policy Number: TST-CL-0002",
        "Clause 1: Room rent is payable up to INR 3,000 per day.",
        "Clause 2: Medicines and injections are payable.",
        "Clause 3: Television and telephone charges are not payable.",
    ]))
    by = {c["section"]: c["interpretation"]["category"] for c in doc["clauses"]}
    assert by == {"1": "limit", "2": "coverage", "3": "exclusion"}


def test_unnumbered_policy_is_split_into_paragraphs(client):
    r = client.post("/api/documents", files={"file": ("plain.pdf", _pdf([
        "Plain Language Health Policy",
        "Room rent is payable up to INR 2,500 per day for each day of the hospital stay.",
        "Medicines, injections and intravenous fluids given in hospital are payable.",
        "Television charges, telephone charges and guest meals are not payable.",
    ]), "application/pdf")}, data={"doc_type": "policy"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert any("numbered its paragraphs" in w for w in out["warnings"])
    doc = client.get(f"/api/documents/{out['document_id']}").json()
    cats = [c["interpretation"]["category"] for c in doc["clauses"]]
    assert [c["section"] for c in doc["clauses"]][:1] == ["P1"] and "limit" in cats and "exclusion" in cats


def test_wrong_files_get_clear_messages(client, tmp_path):
    from demo import test_pack as P
    paths = P.generate(tmp_path)
    up = lambda name, data: client.post("/api/documents", files={"file": (name, data, "application/octet-stream")})
    r = up("bill.pdf", paths["bill"].read_bytes())
    assert r.status_code == 422 and "hospital bill" in r.json()["message"] and "New claim" in r.json()["message"]
    assert "empty" in up("empty.pdf", b"").json()["message"]
    assert "isn't a PDF, JPEG or PNG" in up("notes.txt", b"hello world").json()["message"]
    assert up("brochure.pdf", paths["brochure"].read_bytes()).json()["warnings"] == []
