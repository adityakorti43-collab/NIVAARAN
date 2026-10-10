"""Clause segmentation and document-metadata extraction from extracted page text."""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime
from typing import Optional

from app.models import NOT_FOUND, PageText

CLAUSE_RE = re.compile(r"^((?:[A-Z]\d*)?\d+(?:\.\d+)+)\s+(\S.{0,90})$")
GROUP_RE = re.compile(r"^(Section\s+\d+\b.*|Annexure\s+[IVXLC]+\b.*|Endorsement Provisions.*|Schedule\b.*)$", re.I)
PAGE_NO_RE = re.compile(r"^page\s+\d+(\s+of\s+\d+)?\b", re.I)
META_RE = re.compile(r"^([A-Z][A-Za-z .()/-]{2,40}):\s*(.+)$")

DATE_FORMATS = ["%d-%b-%Y", "%d-%B-%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%d.%m.%Y"]


def parse_date(text: str | None) -> Optional[date]:
    if not text:
        return None
    t = text.strip().rstrip(".")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    m = re.search(r"\b(\d{1,2}[-/ .][A-Za-z]{3,9}[-/ .]\d{4}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4}|\d{4}-\d{2}-\d{2})\b", t)
    if m and m.group(1) != t:
        return parse_date(m.group(1))
    return None


def _repeated_lines(pages: list[PageText]) -> set[str]:
    """Lines that repeat on most pages are running headers/footers, not clause text."""
    if len(pages) < 2:
        return set()
    counts: Counter[str] = Counter()
    for p in pages:
        counts.update({ln.strip() for ln in p.text.splitlines() if ln.strip()})
    threshold = max(2, int(0.6 * len(pages)))
    return {ln for ln, c in counts.items() if c >= threshold}


def clean_lines(pages: list[PageText]) -> list[tuple[int, str]]:
    repeated = _repeated_lines(pages)
    out = []
    for p in pages:
        for ln in p.text.splitlines():
            s = ln.strip()
            if not s or s in repeated or PAGE_NO_RE.match(s) or s.upper().startswith("SYNTHETIC DEMONSTRATION DOCUMENT"):
                continue
            out.append((p.number, s))
    return out


def segment(pages: list[PageText]) -> tuple[list[dict], dict[str, str]]:
    """Split text into clauses. Returns (raw clauses, header metadata key/values)."""
    lines = clean_lines(pages)
    clauses: list[dict] = []
    meta: dict[str, str] = {}
    group = ""
    current: Optional[dict] = None
    preamble = True
    for page_no, line in lines:
        m = CLAUSE_RE.match(line)
        if m and not line.endswith(".") and len(m.group(2).split()) <= 10:
            if current:
                clauses.append(current)
            current = {"section": m.group(1), "heading": m.group(2).strip(), "page": page_no, "group": group, "body": []}
            preamble = False
            continue
        if GROUP_RE.match(line):
            if current:
                clauses.append(current)
                current = None
            group = line
            preamble = False
            continue
        if preamble:
            mm = META_RE.match(line)
            if mm:
                meta[mm.group(1).strip().lower()] = mm.group(2).strip()
            elif "title" not in meta:
                meta["title"] = line
            continue
        if current is not None:
            current["body"].append(line)
    if current:
        clauses.append(current)
    for c in clauses:
        c["text"] = re.sub(r"\s+", " ", " ".join(c.pop("body"))).strip()
        c["text"] = re.sub(r"(\w)- (\w)", r"\1-\2", c["text"])
    return [c for c in clauses if c["text"]], meta


def _get(meta: dict[str, str], *keys: str) -> Optional[str]:
    for k in keys:
        if k in meta:
            return meta[k]
    return None


def parse_inr(text: str | None):
    from app.money import money
    if not text:
        return None
    m = re.search(r"(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)", text) or re.search(r"([\d,]{3,}(?:\.\d+)?)", text)
    return money(m.group(1)) if m else None


def policy_metadata(meta: dict[str, str]) -> dict:
    period = _get(meta, "policy period")
    p_from = p_to = None
    if period:
        parts = re.split(r"\s+to\s+|\s+-\s+", period)
        if len(parts) == 2:
            p_from, p_to = parse_date(parts[0]), parse_date(parts[1])
    si = parse_inr(_get(meta, "sum insured"))
    out = {
        "title": meta.get("title", NOT_FOUND),
        "insurer": _get(meta, "insurer") or NOT_FOUND,
        "policy_number": _get(meta, "policy number", "policy no", "policy no.") or NOT_FOUND,
        "policyholder": _get(meta, "policyholder", "insured", "proposer") or NOT_FOUND,
        "policy_period_from": p_from.isoformat() if p_from else NOT_FOUND,
        "policy_period_to": p_to.isoformat() if p_to else NOT_FOUND,
        "effective_date": (d.isoformat() if (d := parse_date(_get(meta, "policy effective date", "effective date"))) else
                           (p_from.isoformat() if p_from else NOT_FOUND)),
        "continuous_coverage_since": (d.isoformat() if (d := parse_date(_get(meta, "continuous coverage since", "first policy commencement date"))) else NOT_FOUND),
        "sum_insured": str(si) if si is not None else NOT_FOUND,
    }
    return out


def endorsement_metadata(meta: dict[str, str]) -> dict:
    eff = parse_date(_get(meta, "endorsement effective date", "effective date"))
    issue = parse_date(_get(meta, "endorsement issue date", "issue date", "date of issue"))
    applies = _get(meta, "applies to") or NOT_FOUND
    title = meta.get("title", NOT_FOUND)
    num = re.search(r"Endorsement No\.?\s*([A-Z0-9-]+)", title)
    return {
        "title": title,
        "endorsement_number": num.group(1) if num else NOT_FOUND,
        "insurer": _get(meta, "insurer") or NOT_FOUND,
        "policy_number": _get(meta, "policy number") or NOT_FOUND,
        "issue_date": issue.isoformat() if issue else NOT_FOUND,
        "effective_date": eff.isoformat() if eff else NOT_FOUND,
        "applies_to": applies,
        "retrospective": ("no" if re.search(r"on or after", applies, re.I) else
                          "yes" if re.search(r"retrospective", applies, re.I) else "unclear"),
    }
