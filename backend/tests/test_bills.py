import json
from decimal import Decimal as D

import pytest

from app.bills.parse import build_bill, parse_bill_bytes
from app.ingestion.extract import DocumentError


def test_demo_pdf_bill_parsed_exactly(bill):
    assert len(bill.items) == 16
    assert bill.computed_total == D("125900.00") and bill.stated_total == D("125900.00")
    assert bill.issues == []
    first = bill.items[0]
    assert first.description == "Deluxe Room Charges" and first.quantity == D("2") and first.unit_price == D("9000.00")
    assert str(bill.admission_date) == "2025-11-12" and bill.hospital.startswith("Synthetic Care Hospital")


def test_line_arithmetic_mismatch_flagged_and_amount_preserved():
    b = build_bill({"items": [{"description": "Room", "quantity": "2", "unit_price": "1000", "amount": "2500"}], "stated_total": None})
    assert b.items[0].amount == D("2500.00")
    assert any("billed amount is 2,500.00" in i.message for i in b.issues)


def test_total_mismatch_flagged():
    b = build_bill({"items": [{"description": "A", "amount": "100"}, {"description": "B", "amount": "50"}], "stated_total": "200"})
    assert b.computed_total == D("150.00") and any("does not equal" in i.message for i in b.issues)


def test_csv_bill():
    data = b"description,quantity,unit_price,amount,service_date\nUSG Abdomen,1,2500,2500,12-11-2025\nInj. Ceftriaxone,6,400,2400,13-11-2025\n"
    b = build_bill(parse_bill_bytes(data, "csv"))
    assert [i.description for i in b.items] == ["USG Abdomen", "Inj. Ceftriaxone"] and b.computed_total == D("4900.00")


def test_json_bill():
    data = json.dumps({"admission_date": "2025-11-12", "items": [{"description": "ICU", "amount": 12000}]}).encode()
    b = build_bill(parse_bill_bytes(data, "json"))
    assert b.items[0].amount == D("12000.00") and str(b.admission_date) == "2025-11-12"


def test_no_items_rejected():
    with pytest.raises(DocumentError):
        build_bill({"items": [], "stated_total": None})


def test_negative_amount_flagged():
    b = build_bill({"items": [{"description": "Refund", "amount": "-500"}], "stated_total": None})
    assert any(i.severity == "error" and "negative" in i.message for i in b.issues)
