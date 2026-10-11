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


# --- formats beyond "2.1 Heading" -------------------------------------------------------------------------------
# Bracketed clause IDs: "[COV-04] Ambulance — Emergency ground ambulance charges ..."
BRACKET_RE = re.compile(r"^\[([A-Za-z]{1,8}[- ]?\d{1,4}[A-Za-z]?)\]\s*(.+)$")
# "Clause 12: ...", "Article 5 - ...", "Condition 3.2 ..."
WORD_ID_RE = re.compile(r"^(?:Clause|Article|Condition|Benefit|Rule|Exclusion|Provision)\s+(\d+(?:\.\d+)*[A-Za-z]?)\s*[:.\-–—)]?\s*(.*)$", re.I)
# A numbered clause whose wording starts on the same line: "4.1 Room rent is payable up to ..." / "4.1.2 ..."
INLINE_RE = re.compile(r"^((?:[A-Z]\d*)?\d+(?:\.\d+)+)[.)]?\s+(\S.*)$")
# Top-level numbered headings: "1. Policy Schedule", "5) Exclusions", "SECTION 4 - EXCLUSIONS"
TOP_RE = re.compile(r"^(?:section\s+)?(\d{1,2})[.)]?\s+([A-Z][^.]{1,70})$", re.I)
CAPS_HEADING_RE = re.compile(r"^[A-Z][A-Z0-9 &/,()'\-–—]{3,60}$")
# Fonts that map the rupee glyph to "I" or "`" when text is extracted: "I5,000" -> "INR 5,000"
RUPEE_GLYPH_RE = re.compile(r"(?<![A-Za-z0-9])[I`](?=\d{1,3}(?:,\d{2,3})+(?:\.\d+)?\b|\d{4,}\b)")
HEAD_SPLIT_RE = re.compile(r"\s+[—–]\s+|\s+-\s+|:\s+")
# "Label" on one line and its value on the next (schedule tables)
SCHEDULE_LABELS = {
    "policy number": "policy number", "sample policy number": "policy number", "policy no": "policy number", "policy no.": "policy number",
    "policy period": "policy period", "period of insurance": "policy period", "sum insured": "sum insured", "base sum insured": "sum insured",
    "policyholder": "policyholder", "insured person": "policyholder", "policyholder / insured": "policyholder", "proposer": "policyholder",
    "policy effective date": "policy effective date", "effective date": "policy effective date", "commencement date": "policy effective date",
    "insurer": "insurer", "insurance company": "insurer", "continuous coverage since": "continuous coverage since",
    "endorsement number": "endorsement number", "effective from": "endorsement effective date", "issued on": "endorsement issue date",
}


MONTHS = r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"


def _headingish(text: str) -> bool:
    t = text.strip()
    letters = sum(ch.isalpha() for ch in t)
    if letters < 4 or letters < 0.6 * len(t.replace(" ", "")):
        return False
    if re.match(rf"^(?:{MONTHS})[a-z]*\b", t, re.I) or re.search(r"\bINR\b|\d{1,3}(?:,\d{2,3})+", t):
        return False
    return True


def normalise_text(line: str) -> str:
    return RUPEE_GLYPH_RE.sub("INR ", line)


def _split_heading(rest: str) -> tuple[str, str]:
    """'Ambulance — Emergency ambulance charges ...' -> ('Ambulance', 'Emergency ambulance charges ...')."""
    m = HEAD_SPLIT_RE.search(rest)
    if m and 0 < len(rest[:m.start()].split()) <= 10:
        return rest[:m.start()].strip(), rest[m.end():].strip()
    words = rest.split()
    if len(words) <= 10 and not rest.endswith("."):
        return rest.strip(), ""
    return " ".join(words[:6]).rstrip(",;:"), rest.strip()


def _schedule_pairs(lines: list[tuple[int, str]], meta: dict[str, str]) -> None:
    for i, (_, ln) in enumerate(lines[:-1]):
        key = SCHEDULE_LABELS.get(ln.strip().rstrip(":").lower())
        if key and key not in meta:
            meta[key] = lines[i + 1][1].strip()


def _strict(lines: list[tuple[int, str]]) -> tuple[list[dict], dict[str, str]]:
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
    return clauses, meta


def _flexible(lines: list[tuple[int, str]]) -> tuple[list[dict], dict[str, str]]:
    """Any of the common clause styles; top-level numbered or capitalised headings become groups, and text that sits
    directly under a group (with no clause ID of its own) becomes a clause numbered after that group."""
    has_ids = any(BRACKET_RE.match(l) or INLINE_RE.match(l) or WORD_ID_RE.match(l) for _, l in lines)
    clauses: list[dict] = []
    meta: dict[str, str] = {}
    group, group_no = "", ""
    current: Optional[dict] = None
    preamble, title_parts = True, []

    def start(section: str, rest: str, page_no: int) -> dict:
        heading, first = _split_heading(rest)
        return {"section": section, "heading": heading or section, "page": page_no, "group": group, "body": [first] if first else []}

    for page_no, line in lines:
        m = BRACKET_RE.match(line) or WORD_ID_RE.match(line)
        mi = None if m else (CLAUSE_RE.match(line) if not line.endswith(".") and CLAUSE_RE.match(line) and len(line.split()) <= 11 else INLINE_RE.match(line))
        if mi and not _headingish(mi.group(2)[:40]):
            mi = None
        hit = m or mi
        if hit:
            if current:
                clauses.append(current)
            section = hit.group(1).upper().replace(" ", "-") if m else hit.group(1)
            current = start(section, hit.group(2), page_no)
            preamble = False
            continue
        top = TOP_RE.match(line) if has_ids else None
        if top and not _headingish(top.group(2)):
            top = None
        caps = CAPS_HEADING_RE.match(line) and _headingish(line) and not preamble and len(line.split()) <= 8
        if top or GROUP_RE.match(line) or caps:
            if current:
                clauses.append(current)
            current = None
            group, group_no = line, (top.group(1) if top else "")
            preamble = False
            continue
        if preamble:
            mm = META_RE.match(line)
            if mm:
                meta[mm.group(1).strip().lower()] = mm.group(2).strip()
            elif len(title_parts) < 4 and len(line.split()) <= 8 and (not title_parts or line.isupper() == title_parts[-1].isupper()):
                title_parts.append(line)
            continue
        if current is None and group:
            # text directly under a heading: one clause per group, numbered after the group ("7", or "G3" if unnumbered)
            current = {"section": group_no or f"G{len(clauses) + 1}", "heading": re.sub(r"^(?:section\s+)?\d+[.)]?\s*", "", group, flags=re.I),
                       "page": page_no, "group": group, "body": []}
        if current is not None:
            current["body"].append(line)
    if current:
        clauses.append(current)
    if title_parts:
        meta["title"] = " ".join(title_parts)
    return clauses, meta


def _paragraphs(lines: list[tuple[int, str]]) -> tuple[list[dict], dict[str, str]]:
    """Last resort for documents with no clause numbers at all: each paragraph becomes P1, P2, ... under the most
    recent heading, so every statement can still be cited by document, page and exact text."""
    clauses: list[dict] = []
    meta: dict[str, str] = {}
    group = ""
    body: list[str] = []
    page = lines[0][0] if lines else 1

    def flush():
        nonlocal body
        text = " ".join(body).strip()
        if len(text.split()) >= 4:
            first = re.split(r"(?<=[.;:])\s", text, maxsplit=1)[0]
            clauses.append({"section": f"P{len(clauses) + 1}", "heading": " ".join(first.split()[:7]).rstrip(",;:."), "page": page,
                            "group": group, "body": [text]})
        body = []

    for i, (page_no, line) in enumerate(lines):
        if i == 0:
            meta["title"] = line
            continue
        mm = META_RE.match(line)
        if mm and not clauses and not body:
            meta[mm.group(1).strip().lower()] = mm.group(2).strip()
            continue
        tm = TOP_RE.match(line)
        if ((CAPS_HEADING_RE.match(line) and _headingish(line)) or (tm and _headingish(tm.group(2)))) and len(line.split()) <= 8:
            flush()
            group = line
            continue
        if not body:
            page = page_no
        body.append(line)
        if re.search(r"[.;]$", line) and len(" ".join(body).split()) >= 5:
            flush()
    flush()
    return clauses, meta


def segment(pages: list[PageText]) -> tuple[list[dict], dict[str, str]]:
    """Split text into clauses. Returns (raw clauses, header metadata key/values).

    Tries, in order: the "2.1 Heading" style; any common clause style (bracketed IDs, inline numbering, "Clause 12",
    numbered/capitalised section headings); and finally paragraph numbering (P1, P2, ...). meta["_segmentation"]
    records which was used so the upload can say so."""
    lines = [(p, normalise_text(l)) for p, l in clean_lines(pages)]
    def run(fn):
        cl, md = fn(lines)
        for c in cl:
            c["text"] = re.sub(r"\s+", " ", " ".join(c.get("body", []))).strip()
            c["text"] = re.sub(r"(\w)- (\w)", r"\1-\2", c["text"])
        return [c for c in cl if c["text"]], md

    # The classic "2.1 Heading" reading is kept unless a more flexible reading finds more clauses (short endorsements
    # often have a single numbered clause); paragraph numbering is used only when nothing else finds any.
    clauses, meta = run(_strict)
    mode = "numbered"
    if len(clauses) < 3:
        flex, fmeta = run(_flexible)
        if len(flex) > len(clauses):
            clauses, meta, mode = flex, fmeta, "flexible"
    if not clauses:
        clauses, meta = run(_paragraphs)
        mode = "paragraphs"
    for c in clauses:
        c.pop("body", None)
    _schedule_pairs(lines, meta)
    meta["_segmentation"] = mode
    return clauses, meta


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
        parts = re.split(r"\s+to\s+|\s+[-–—]\s+", period)
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
