"""Itemised bill ingestion (PDF table, CSV, JSON, or manual entry) with arithmetic validation.

Original descriptions and amounts are preserved exactly. Discrepancies are flagged, never corrected.
"""
from __future__ import annotations

import csv
import io
import json
import re
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from app.ingestion.extract import DocumentError, check_size, pdf_words
from app.ingestion.segment import parse_date
from app.models import NOT_FOUND, Bill, BillIssue, BillItem
from app.money import ZERO, fmt, money, q

NUM_RE = re.compile(r"^-?[\d,]+(?:\.\d+)?$")
DATE_RE = re.compile(r"^\d{1,2}[-/.]\d{1,2}[-/.]\d{4}$|^\d{4}-\d{2}-\d{2}$|^\d{1,2}-[A-Za-z]{3}-\d{4}$")
META_KEYS = {"patient": "patient", "bill date": "bill_date", "admission date": "admission_date",
             "discharge date": "discharge_date", "diagnosis": "diagnosis"}


def _lines(words: list[tuple[float, float, str]], tol: float = 3.0) -> list[list[tuple[float, str]]]:
    rows: list[tuple[float, list[tuple[float, str]]]] = []
    for x, y, w in sorted(words, key=lambda t: (round(t[1]), t[0])):
        for row in rows:
            if abs(row[0] - y) <= tol:
                row[1].append((x, w))
                break
        else:
            rows.append((y, [(x, w)]))
    return [sorted(r[1]) for r in sorted(rows, key=lambda r: r[0])]


def _num(s: str) -> Optional[Decimal]:
    if not NUM_RE.match(s):
        return None
    try:
        return Decimal(s.replace(",", ""))
    except InvalidOperation:
        return None


def parse_pdf_bill(data: bytes) -> dict[str, Any]:
    pages = pdf_words(data)
    meta: dict[str, Any] = {}
    items: list[dict] = []
    stated_total = None
    first_line = None
    for words in pages:
        for line in _lines(words):
            toks = [w for _, w in line]
            text = " ".join(toks)
            if first_line is None and not text.upper().startswith("SYNTHETIC DEMONSTRATION"):
                first_line = text
            if ":" in text and not NUM_RE.match(toks[0]):
                key, _, val = text.partition(":")
                k = key.strip().lower()
                if k in META_KEYS:
                    meta[META_KEYS[k]] = val.strip()
                continue
            if re.match(r"^(grand\s+)?total(\s+amount)?\b", text, re.I) and _num(toks[-1]) is not None:
                stated_total = toks[-1]
                continue
            if len(toks) >= 5 and toks[0].isdigit() and all(_num(t) is not None for t in toks[-3:]):
                qty, rate, amount = toks[-3:]
                rest = toks[1:-3]
                sdate = None
                if rest and DATE_RE.match(rest[-1]):
                    sdate = rest[-1]
                    rest = rest[:-1]
                if not rest:
                    continue
                items.append({"line_no": int(toks[0]), "description": " ".join(rest), "service_date": sdate,
                              "quantity": qty, "unit_price": rate, "amount": amount})
    if first_line:
        meta.setdefault("hospital", first_line.split(" - ")[0])
    return {"meta": meta, "items": items, "stated_total": stated_total}


def parse_csv_bill(data: bytes) -> dict[str, Any]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentError("CSV bill must be UTF-8 text.", "unsupported_type") from exc
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "description" not in [f.strip().lower() for f in reader.fieldnames]:
        raise DocumentError("CSV bill must have a header row with at least 'description' and 'amount' columns.",
                            "bill_format")
    items = []
    for i, row in enumerate(reader, start=1):
        r = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        if not r.get("description"):
            continue
        items.append({"line_no": i, "description": r["description"], "service_date": r.get("service_date") or None,
                      "quantity": r.get("quantity") or "1", "unit_price": r.get("unit_price") or None,
                      "amount": r.get("amount", ""), "category": r.get("category") or None})
    return {"meta": {}, "items": items, "stated_total": None}


def parse_json_bill(data: bytes) -> dict[str, Any]:
    try:
        obj = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DocumentError("JSON bill could not be parsed.", "bill_format") from exc
    if isinstance(obj, list):
        obj = {"items": obj}
    items = obj.get("items")
    if not isinstance(items, list):
        raise DocumentError("JSON bill must contain an 'items' list.", "bill_format")
    norm = [{"line_no": i, **{k: (str(v) if isinstance(v, (int, float)) else v) for k, v in it.items()}}
            for i, it in enumerate(items, start=1) if isinstance(it, dict)]
    meta = {k: obj[k] for k in ("hospital", "patient", "bill_date", "admission_date", "discharge_date", "diagnosis") if k in obj}
    return {"meta": meta, "items": norm, "stated_total": obj.get("total")}


def build_bill(raw: dict[str, Any], document_id: Optional[str] = None, synthetic: bool = False) -> Bill:
    issues: list[BillIssue] = []
    items: list[BillItem] = []
    for it in raw["items"]:
        ln = int(it.get("line_no") or len(items) + 1)
        desc = str(it.get("description", "")).strip()
        try:
            amount = money(str(it.get("amount", "")))
        except ValueError:
            issues.append(BillIssue(severity="error", line_no=ln, message=f"Line {ln} ('{desc}') has no valid amount; it was not included."))
            continue
        if amount < 0:
            issues.append(BillIssue(severity="error", line_no=ln, message=f"Line {ln} has a negative amount ({fmt(amount)}); credits must be reviewed manually."))
        try:
            qty = Decimal(str(it.get("quantity") or "1").replace(",", ""))
        except InvalidOperation:
            qty = Decimal("1")
            issues.append(BillIssue(severity="warning", line_no=ln, message=f"Line {ln} quantity unreadable; treated as 1 for display only."))
        rate = None
        if it.get("unit_price"):
            try:
                rate = money(str(it["unit_price"]))
            except ValueError:
                issues.append(BillIssue(severity="warning", line_no=ln, message=f"Line {ln} unit rate unreadable."))
        if rate is not None and q(rate * qty) != amount:
            issues.append(BillIssue(severity="error", line_no=ln,
                                    message=f"Line {ln} ('{desc}'): quantity {qty} x rate {fmt(rate)} = {fmt(q(rate * qty))}, "
                                            f"but the billed amount is {fmt(amount)}. The billed amount is kept unchanged."))
        sdate = parse_date(it.get("service_date")) if it.get("service_date") else None
        if it.get("service_date") and not sdate:
            issues.append(BillIssue(severity="warning", line_no=ln, message=f"Line {ln} service date '{it['service_date']}' could not be read."))
        items.append(BillItem(item_id=f"L{ln:02d}", line_no=ln, description=desc, service_date=sdate, quantity=qty,
                              unit_price=rate, amount=amount, category_hint=it.get("category")))
    if not items:
        raise DocumentError("No itemised charges could be read from the bill. Upload an itemised bill (PDF table, "
                            "CSV or JSON) or enter the items manually.", "bill_no_items")
    computed = sum((i.amount for i in items), ZERO)
    stated = None
    if raw.get("stated_total") not in (None, ""):
        try:
            stated = money(str(raw["stated_total"]))
        except ValueError:
            issues.append(BillIssue(severity="warning", message="Stated bill total could not be read."))
    if stated is not None and stated != computed:
        issues.append(BillIssue(severity="error", message=f"Sum of line items ({fmt(computed)}) does not equal the stated "
                                                          f"bill total ({fmt(stated)}). Line amounts are used; please verify the bill."))
    meta = raw.get("meta", {})
    return Bill(bill_id=f"bill-{uuid.uuid4().hex[:10]}", document_id=document_id,
                hospital=meta.get("hospital", NOT_FOUND), patient=meta.get("patient", NOT_FOUND),
                bill_date=parse_date(meta.get("bill_date")), admission_date=parse_date(meta.get("admission_date")),
                discharge_date=parse_date(meta.get("discharge_date")), diagnosis=meta.get("diagnosis", NOT_FOUND),
                items=items, stated_total=stated, computed_total=computed, issues=issues, synthetic=synthetic)


def _snapshot(i: BillItem) -> dict[str, Optional[str]]:
    return {"description": i.description, "quantity": str(i.quantity), "unit_price": None if i.unit_price is None else str(i.unit_price),
            "amount": str(i.amount), "service_date": i.service_date.isoformat() if i.service_date else None}


def revise_bill(bill: Bill, edits: list[dict[str, Any]], reviewed_at: Optional[str] = None) -> tuple[Bill, list[str]]:
    """Apply user corrections to a bill.

    Totals and arithmetic checks are recomputed here (client-supplied totals are never trusted). Existing lines keep
    their item IDs; a changed line becomes `user_corrected` and keeps its originally extracted values; new lines are
    `manual`; removed lines are kept in `removed_items`. Returns the revised bill and a description of each change.
    """
    before = {i.item_id: i for i in bill.items}
    next_ln = max([i.line_no for i in bill.items + bill.removed_items] or [0]) + 1
    raw_items = []
    for e in edits:
        orig = before.get(str(e.get("item_id") or ""))
        ln = orig.line_no if orig else next_ln
        if not orig:
            next_ln += 1
        raw_items.append({"line_no": ln, "description": e.get("description", ""), "amount": e.get("amount"),
                          "quantity": e.get("quantity") or "1", "unit_price": e.get("unit_price"),
                          "service_date": e.get("service_date"), "category": (orig.category_hint if orig else e.get("category"))})
    new = build_bill({"items": raw_items, "stated_total": None if bill.stated_total is None else str(bill.stated_total)},
                     document_id=bill.document_id, synthetic=bill.synthetic)
    changes: list[str] = []
    items = []
    for it in new.items:
        orig = before.get(it.item_id)
        if orig is None:
            it.source = "manual"
            changes.append(f"line {it.line_no} added ({it.description}, {fmt(it.amount)})")
        elif _snapshot(orig) != _snapshot(it):
            it.source = "manual" if orig.source == "manual" else "user_corrected"
            it.extracted = orig.extracted or (_snapshot(orig) if orig.source == "extracted" else None)
            diffs = [f"{k.replace('_', ' ')} {a} -> {b}" for k, a, b in
                     ((k, _snapshot(orig)[k], _snapshot(it)[k]) for k in _snapshot(it)) if a != b]
            changes.append(f"line {it.line_no} corrected ({'; '.join(diffs)})")
        else:
            it.source, it.extracted = orig.source, orig.extracted
        items.append(it)
    kept = {i.item_id for i in items}
    removed = list(bill.removed_items)
    for i in bill.items:
        if i.item_id not in kept:
            removed.append(i)
            changes.append(f"line {i.line_no} removed ({i.description}, {fmt(i.amount)})")
    revised = bill.model_copy(update={"items": items, "computed_total": new.computed_total, "issues": new.issues,
                                      "removed_items": removed, "reviewed_at": reviewed_at or bill.reviewed_at})
    return revised, changes


def parse_bill_bytes(data: bytes, kind: str) -> dict[str, Any]:
    check_size(data)
    if kind == "pdf":
        return parse_pdf_bill(data)
    if kind == "csv":
        return parse_csv_bill(data)
    if kind == "json":
        return parse_json_bill(data)
    raise DocumentError("Unsupported bill format.", "unsupported_type")
