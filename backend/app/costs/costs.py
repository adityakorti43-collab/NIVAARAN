"""Treatment-cost intelligence over an explicitly illustrative dataset or user-entered amounts.

The cost table is synthetic and labelled as such. Estimates of policy outcome are produced by running a
HYPOTHETICAL bill through the same adjudication pipeline as real claims.
"""
from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from functools import lru_cache
from typing import Optional

from app.config import BACKEND_DIR
from app.models import Bill, BillItem, Claim, DocumentRecord
from app.money import ZERO, allocate, money, q

DATA = BACKEND_DIR / "data" / "costs" / "illustrative_costs.json"


@lru_cache(maxsize=1)
def dataset() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def procedure(key: str) -> dict:
    p = next((p for p in dataset()["procedures"] if p["key"] == key), None)
    if not p:
        raise KeyError(key)
    return p


def ranges(key: str, hospital_type: str) -> dict:
    p = procedure(key)
    mult = Decimal(dataset()["hospital_types"][hospital_type]["multiplier"])
    return {tier: {"p25": str(q(money(v[0]) * mult)), "median": str(q(money(v[1]) * mult)), "p75": str(q(money(v[2]) * mult))}
            for tier, v in p["tiers"].items()}


def build_hypothetical_bill(key: str, total: Decimal, room_days: Optional[int] = None,
                            icu_days: Optional[int] = None, admission: Optional[date] = None) -> Bill:
    p = procedure(key)
    room_days = room_days if room_days is not None else p["typical_room_days"]
    icu_days = icu_days if icu_days is not None else p["typical_icu_days"]
    shares = [Decimal(s) for _, s in p["components"]]
    parts = allocate(q(total), shares)
    items = []
    for i, ((desc, _), amt) in enumerate(zip(p["components"], parts), start=1):
        qty = Decimal(room_days if desc.startswith("Room") else icu_days if desc.startswith("ICU") else 1)
        qty = qty if qty > 0 else Decimal(1)
        items.append(BillItem(item_id=f"H{i:02d}", line_no=i, description=desc, service_date=admission,
                              quantity=qty, unit_price=q(amt / qty) if q(amt / qty) * qty == amt else None, amount=amt))
    return Bill(bill_id=f"hyp-{uuid.uuid4().hex[:8]}", hospital="HYPOTHETICAL (illustrative cost table)",
                patient="HYPOTHETICAL", items=items, computed_total=sum(parts, ZERO), synthetic=True,
                admission_date=admission, discharge_date=admission, diagnosis=p["name"])


def estimate(key: str, total: Decimal, policy: DocumentRecord, endorsements: list[DocumentRecord],
             docs: dict[str, DocumentRecord], treatment_date: date, room_days: Optional[int] = None,
             icu_days: Optional[int] = None, source: str = "illustrative") -> dict:
    from app.adjudication.adjudicate import adjudicate
    bill = build_hypothetical_bill(key, total, room_days, icu_days, treatment_date)
    claim = Claim(claim_id="hypothetical-cost", title=f"HYPOTHETICAL — {procedure(key)['name']}", policy_document_id=policy.document_id,
                  endorsement_ids=[e.document_id for e in endorsements], bill=bill, admission_date=treatment_date,
                  discharge_date=treatment_date, diagnosis=procedure(key)["name"], synthetic=True)
    a = adjudicate(claim, docs, cause="Treatment cost intelligence (hypothetical)")
    return {"source": source, "label": "HYPOTHETICAL estimate from an " + ("illustrative synthetic cost table" if source == "illustrative"
                                                                            else "amount you entered"),
            "total": str(q(total)), "analysis": a.model_dump(mode="json")}
