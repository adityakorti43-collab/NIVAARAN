"""Unit tests for app/costs/costs.py: the pure helpers behind the treatment-cost feature.
(test_api.py already covers the end-to-end /api/costs/estimate labelling.)"""
from decimal import Decimal as D

import pytest

from app.costs.costs import build_hypothetical_bill, dataset, procedure, ranges

# Every procedure in the illustrative dataset, so new procedures are tested automatically
ALL_KEYS = [p["key"] for p in dataset()["procedures"]]


def test_procedure_unknown_key_raises():
    with pytest.raises(KeyError):
        procedure("not_a_real_procedure")


def test_ranges_apply_hospital_multiplier():
    # lap_appendicectomy tier1 p25 is 95,000 at a private hospital (multiplier 1.00)
    private = ranges("lap_appendicectomy", "private")["tier1"]
    assert private["p25"] == "95000.00"
    # trust hospitals are 0.70x and public hospitals 0.35x of the private figure
    assert ranges("lap_appendicectomy", "trust")["tier1"]["p25"] == "66500.00"
    assert ranges("lap_appendicectomy", "public")["tier1"]["p25"] == "33250.00"


def test_ranges_are_ordered_p25_median_p75():
    for tier in ranges("lap_appendicectomy", "private").values():
        assert D(tier["p25"]) <= D(tier["median"]) <= D(tier["p75"])


def test_hypothetical_bill_is_labelled_synthetic():
    bill = build_hypothetical_bill("lap_appendicectomy", D("100000"))
    # A hypothetical bill must never be mistaken for a real patient's bill
    assert bill.synthetic is True
    assert bill.patient == "HYPOTHETICAL"
    assert bill.hospital.startswith("HYPOTHETICAL")


@pytest.mark.parametrize("key", ALL_KEYS)
def test_hypothetical_bill_items_reconcile_to_total(key):
    # 123,456.78 doesn't split evenly, so this exercises the largest-remainder rounding
    bill = build_hypothetical_bill(key, D("123456.78"))
    assert sum(i.amount for i in bill.items) == D("123456.78")
    assert bill.computed_total == D("123456.78")


def test_hypothetical_bill_uses_room_days_as_room_quantity():
    bill = build_hypothetical_bill("lap_appendicectomy", D("100000"), room_days=3)
    room = next(i for i in bill.items if i.description.startswith("Room"))
    assert room.quantity == D("3")


def test_hypothetical_bill_zero_days_falls_back_to_quantity_one():
    # Quantity 0 would divide by zero when computing unit price, so it falls back to 1
    bill = build_hypothetical_bill("lap_appendicectomy", D("100000"), room_days=0, icu_days=0)
    assert all(i.quantity == D("1") for i in bill.items)
    