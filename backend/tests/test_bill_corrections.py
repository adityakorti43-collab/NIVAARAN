"""User corrections to extracted bill lines: provenance, preserved originals, recomputed totals, re-analysis."""
from decimal import Decimal

from fastapi.testclient import TestClient

from app.bills.parse import revise_bill
from app.main import app


def edits_of(bill):
    return [{"item_id": i.item_id, "description": i.description, "amount": str(i.amount), "quantity": str(i.quantity),
             "unit_price": None if i.unit_price is None else str(i.unit_price),
             "service_date": i.service_date.isoformat() if i.service_date else None} for i in bill.items]


def test_unchanged_bill_has_no_changes(bill):
    revised, changes = revise_bill(bill, edits_of(bill))
    assert changes == []
    assert revised.computed_total == bill.computed_total
    assert all(i.source == "extracted" and i.extracted is None for i in revised.items)


def test_correction_keeps_original_and_recomputes_total(bill):
    e = edits_of(bill)
    tv = next(x for x in e if "TV" in x["description"] or "Telephone" in x["description"])
    old_amount = Decimal(tv["amount"])
    tv["amount"], tv["unit_price"] = str(old_amount - 100), None
    revised, changes = revise_bill(bill, e)
    line = next(i for i in revised.items if i.item_id == tv["item_id"])
    assert line.source == "user_corrected"
    assert line.extracted["amount"] == str(old_amount)              # originally extracted value preserved
    assert revised.computed_total == bill.computed_total - 100
    assert len(changes) == 1 and "corrected" in changes[0]
    # correcting again never overwrites the original extraction
    e2 = edits_of(revised)
    next(x for x in e2 if x["item_id"] == tv["item_id"])["amount"] = "1.00"
    again, _ = revise_bill(revised, e2)
    assert next(i for i in again.items if i.item_id == tv["item_id"]).extracted["amount"] == str(old_amount)


def test_add_and_remove_lines(bill):
    e = edits_of(bill)
    removed = e.pop(0)
    e.append({"description": "Dressing charges", "amount": "450.00"})
    revised, changes = revise_bill(bill, e)
    assert removed["item_id"] not in {i.item_id for i in revised.items}
    assert revised.removed_items[0].item_id == removed["item_id"]   # kept for the audit trail
    new = next(i for i in revised.items if i.description == "Dressing charges")
    assert new.source == "manual" and new.line_no > max(i.line_no for i in bill.items)
    assert revised.computed_total == bill.computed_total - Decimal(removed["amount"]) + Decimal("450.00")
    assert any("added" in c for c in changes) and any("removed" in c for c in changes)


def test_stated_total_mismatch_is_flagged_after_correction(bill):
    assert bill.stated_total == bill.computed_total
    e = edits_of(bill)
    e[0]["amount"] = str(Decimal(e[0]["amount"]) + 1)
    revised, _ = revise_bill(bill, e)
    assert any("does not equal the stated" in i.message for i in revised.issues)


def test_api_correction_reanalyses_and_ignores_client_totals():
    c = TestClient(app)
    demo = c.post("/api/demo/enter").json()
    cid = demo["claim_id"]
    claim = c.get(f"/api/claims/{cid}").json()["claim"]
    items = claim["bill"]["items"]
    tv = next(i for i in items if "TV" in i["description"] or "Telephone" in i["description"])
    body = [{"item_id": i["item_id"], "description": i["description"], "amount": i["amount"], "quantity": i["quantity"],
             "unit_price": i["unit_price"], "service_date": i["service_date"]} for i in items]
    next(x for x in body if x["item_id"] == tv["item_id"]).update(amount="0.00", unit_price=None)
    r = c.patch(f"/api/claims/{cid}", json={"bill_items": body, "confirm_bill": True})
    assert r.status_code == 200, r.text
    out = r.json()
    assert "Bill corrected by user" in out["analysis"]["cause"]
    assert out["claim"]["bill"]["reviewed_at"]
    assert Decimal(out["claim"]["bill"]["computed_total"]) == Decimal(claim["bill"]["computed_total"]) - Decimal(tv["amount"])
    # a forged computed_total in a legacy full-bill update is ignored: totals are recomputed on the server
    forged = out["claim"]["bill"] | {"computed_total": "1.00"}
    r2 = c.patch(f"/api/claims/{cid}", json={"bill": forged, "cause": "forged total"})
    assert r2.status_code == 400 or Decimal(r2.json()["claim"]["bill"]["computed_total"]) != Decimal("1.00")
    # another user cannot correct this bill
    other = TestClient(app)
    other.post("/api/demo/enter")
    assert other.patch(f"/api/claims/{cid}", json={"bill_items": body}).status_code == 404
