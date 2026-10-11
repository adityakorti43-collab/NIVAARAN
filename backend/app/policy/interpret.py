"""Deterministic, pattern-based structured interpretation of policy clauses.

Each structured field is derived from the clause's own text. When a pattern does not match, the field
stays empty — the interpreter never fills gaps with generic insurance assumptions. This works best on
clearly drafted wordings; unusual phrasing degrades to category `other`, which downstream code treats
as "no usable evidence" rather than as coverage.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Optional

from app.models import ClauseCategory as Cat
from app.models import Interpretation, LimitSpec
from app.money import money

PAYABLE_RE = re.compile(r"\b(?:is|are)\s+(not\s+)?(?:payable|eligible|covered|admissible|reimbursable|reimbursed)\b", re.I)
EXCLUDED_RE = re.compile(r"\b(?:is|are)\s+(?:excluded|not\s+covered|not\s+eligible|not\s+admissible)\b", re.I)
SUBJECT_END_RE = re.compile(r"\b(?:is|are)\s+(?:not\s+)?(?:payable|eligible|covered|admissible|reimbursable|reimbursed|excluded|"
                            r"limited|capped|restricted|subject to)\b", re.I)
LIMIT_RE = re.compile(
    r"(?:up to|limited to|maximum of|not exceeding|capped at)\s+(?:(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*%\s*of\s+(?:the\s+)?sum insured)"
    r"(?:\s+(?:per|for each|each)\s+(day|hospitali[sz]ation|eye|policy year|policy period|claim|accident|admission|illness))?", re.I)
TRAILING_RE = re.compile(
    r"\s+(?:attending|performed|administered|used|incurred|listed|contracted|arising|during|for the same|"
    r"subject to|in the|consumed|provided|related to|relating to|to transport)\b.*$", re.I)
CONDITION_KEYS = [
    (re.compile(r"prescri", re.I), "vitamin_prescription"),
    (re.compile(r"implant invoice|barcode sticker", re.I), "implant_invoice_submitted"),
    (re.compile(r"injury|accident", re.I), "accident"),
    (re.compile(r"same condition", re.I), "post_hospitalisation_same_condition"),
    (re.compile(r"pre-existing", re.I), "pre_existing_condition"),
]
ORDER_KEYS = [
    ("sum_insured_cap", re.compile(r"sum insured", re.I)),
    ("copay", re.compile(r"co-?payment", re.I)),
    ("deductible", re.compile(r"deductible", re.I)),
    ("item_limit", re.compile(r"limit", re.I)),
    ("exclusion", re.compile(r"exclusion|non-payable", re.I)),
]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[A-Z(])", text) if s.strip()]


def _split_terms(fragment: str) -> list[str]:
    fragment = re.sub(r"\([^)]*\)", " ", fragment)
    parts = re.split(r",|\band\b|\bor\b|/", fragment)
    terms = []
    for p in parts:
        p = re.sub(r"\s+(?:prescribed|required|recommended|advised|used|administered|provided|performed|incurred|undertaken)\b.*$", "", p, flags=re.I)
        p = TRAILING_RE.sub("", p).strip(" .;:-")
        p = re.sub(r"^(?:the|any|all|such|other)\s+", "", p, flags=re.I)
        p = re.sub(r"^(?:(?:medically necessary|reasonable(?: and customary)?|eligible|emergency|ground|road)\s+)+", "", p, flags=re.I)
        if p and len(p) < 60 and not re.match(r"(?:up to|within)\b|\d", p, re.I):
            terms.append(p.lower())
    return terms


def scope_terms(sentence: str, heading: str) -> list[str]:
    s = re.sub(r"^Notwithstanding [^,]+,\s*", "", sentence, flags=re.I)
    m = re.search(r"\bwill pay\b.*?\bfor\s+(.+?)(?:,\s*subject to|\.|$)", s, re.I)
    if m:
        subject = m.group(1)
    else:
        m = SUBJECT_END_RE.search(s)
        subject = s[:m.start()] if m else ""
        if not subject:
            m2 = re.match(r"^(.+?)\s+means\b", s, re.I)
            subject = m2.group(1) if m2 else heading
    terms: list[str] = []
    inc = re.search(r"\b(?:including|such as)\s+(.+)$", subject, re.I)
    if inc:
        terms += _split_terms(inc.group(1))
        subject = subject[:inc.start()]
    terms = _split_terms(subject) + terms
    seen, out = set(), []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def parse_limit(text: str) -> Optional[LimitSpec]:
    m = LIMIT_RE.search(text)
    if not m:
        return None
    basis_raw = (m.group(3) or "").lower()
    basis = {"day": "per_day", "eye": "per_eye", "policy year": "per_policy_year", "policy period": "per_policy_year", "claim": "per_claim",
             "illness": "per_claim", "accident": "per_hospitalisation", "admission": "per_hospitalisation"}.get(
        basis_raw, "per_hospitalisation" if basis_raw.startswith("hospitali") else "unspecified")
    return LimitSpec(amount=money(m.group(1)) if m.group(1) else None,
                     percent_of_sum_insured=Decimal(m.group(2)) if m.group(2) else None,
                     basis=basis, text=m.group(0))


def _condition(text: str) -> tuple[Optional[str], Optional[str]]:
    m = re.search(r"\b(unless|provided|except|only if|only when|subject to the condition that)\b\s+(.+?)(?:\.|$)", text, re.I)
    if not m:
        return None, None
    cond = f"{m.group(1)} {m.group(2)}".strip()
    for rx, key in CONDITION_KEYS:
        if rx.search(cond):
            return cond, key
    return cond, None


def interpret(heading: str, text: str, group: str = "") -> Interpretation:
    notes: list[str] = []
    replaces = re.findall(r"replaces clause\s+([A-Z]?\d+(?:\.\d+)+)", text, re.I)
    overrides: list[str] = []
    nw = re.match(r"^Notwithstanding\s+([^,]+),", text, re.I)
    if nw:
        overrides = [t.strip() for t in re.split(r",|\band\b", re.sub(r"\bclauses?\b", "", nw.group(1), flags=re.I)) if t.strip()]
    sentences = [s for s in _sentences(text) if not re.search(r"replaces clause", s, re.I)]
    cands = [s for s in sentences if not re.match(r"^(?:any\s+)?(?:amount|charges?|excess)\s+(?:above|beyond|exceeding|in excess)", s, re.I)]
    main = next((s for s in cands if re.search(r"payable|eligible|covered|admissible|limited to|excluded|will pay|\bmeans\b|applies|apply|prevails|order", s, re.I)),
                (cands or sentences or [text])[0])
    lower = text.lower()
    kw = dict(scope_terms=scope_terms(main, heading), replaces=replaces, overrides=overrides, notes=notes)

    if re.search(r"\bmeans\b", main) and ("definition" in group.lower() or re.match(r"^[\w\s-]+\s+means\b", main)):
        return Interpretation(category=Cat.definition, **kw)
    if "following order" in lower or "order of computation" in heading.lower():
        order = []
        for item in re.split(r"\([a-z]\)", text)[1:]:
            for key, rx in ORDER_KEYS:
                if rx.search(item):
                    order.append(key)
                    break
        if not order:
            notes.append("Computation order clause found but stages could not be parsed.")
        return Interpretation(category=Cat.computation_order, order=order, **{**kw, "scope_terms": []})
    if "prevails over" in lower:
        return Interpretation(category=Cat.precedence, **{**kw, "scope_terms": []})
    if "retrospective" in lower:
        return Interpretation(category=Cat.applicability, **{**kw, "scope_terms": []})
    if m := re.search(r"deductible of\s+(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)", text, re.I):
        basis = "per_policy_year" if "per policy year" in lower else ("per_claim" if "per claim" in lower else "unspecified")
        return Interpretation(category=Cat.deductible, amount=money(m.group(1)),
                              limit=LimitSpec(amount=money(m.group(1)), basis=basis, text=m.group(0)),
                              **{**kw, "scope_terms": []})
    if "deductible" in heading.lower() and (m := re.search(r"(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)", text)):
        basis = "per_policy_year" if re.search(r"per (?:policy )?year|policy period", lower) else ("per_claim" if "claim" in lower else "unspecified")
        return Interpretation(category=Cat.deductible, amount=money(m.group(1)),
                              limit=LimitSpec(amount=money(m.group(1)), basis=basis, text=m.group(0)), **{**kw, "scope_terms": []})
    if m := re.search(r"co-?payment of\s+(\d+(?:\.\d+)?)\s*%", text, re.I):
        return Interpretation(category=Cat.copayment, percent=Decimal(m.group(1)), **{**kw, "scope_terms": []})
    if re.search(r"co-?pay", heading, re.I) and (m := re.search(r"(\d+(?:\.\d+)?)\s*%", text)):
        return Interpretation(category=Cat.copayment, percent=Decimal(m.group(1)), **{**kw, "scope_terms": []})
    if re.search(r"endorsement", heading + " " + group, re.I) and not re.search(r"replaces clause|notwithstanding", text, re.I) \
            and "endorsement" not in (group + heading).lower().split("provisions")[0][-12:]:
        if re.search(r"supersedes|amended wording|effective from", lower):
            notes.append("Endorsement wording inside the policy document. Upload the endorsement as its own document so it is applied "
                         "only from its effective date.")
            return Interpretation(category=Cat.other, **kw)
    if re.search(r"claim documents? must", lower) or (re.search(r"\bclaims?\b", group, re.I) and re.search(r"document|notif|intimat|procedure|submit", heading + " " + group, re.I)):
        return Interpretation(category=Cat.claim_requirement, **kw)
    if m := re.search(r"payable only after\s+(\d+)\s+months", text, re.I):
        cond, key = _condition(text)
        return Interpretation(category=Cat.waiting_period, payable=False, waiting_months=int(m.group(1)),
                              condition_key=key or ("pre_existing_condition" if "pre-existing" in lower else None), **kw)
    if (m := re.search(r"(\d+)[- ]months?\s+waiting period|waiting period of\s+(\d+)\s+months", text, re.I)) and \
            not re.search(r"first\s+\d+\s+days", text, re.I):
        cond, key = _condition(text)
        months = int(m.group(1) or m.group(2))
        return Interpretation(category=Cat.waiting_period, payable=False, waiting_months=months,
                              condition_key=key if key in ("pre_existing_condition",) else ("pre_existing_condition" if "pre-existing" in lower else None), **kw)
    if (m := re.search(r"(?:during|within)\s+the\s+first\s+(\d+)\s+days|(\d+)[- ]days?\s+waiting period", text, re.I)) and \
            re.search(r"waiting|commencement|policy start|inception", heading + " " + text, re.I):
        cond, key = _condition(text)
        if re.search(r"accident", text, re.I):
            cond, key = cond or "except treatment required because of an accident", "accident"
        return Interpretation(category=Cat.waiting_period, payable=False, waiting_days=int(m.group(1) or m.group(2)),
                              condition=cond, condition_key=key, **kw)
    if m := re.search(r"within\s+(\d+)\s+days of the first policy", text, re.I):
        cond, key = _condition(text)
        return Interpretation(category=Cat.waiting_period, payable=False, waiting_days=int(m.group(1)),
                              condition=cond, condition_key=key, **kw)
    before = re.search(r"(\d+)\s+days before admission", text, re.I)
    after = re.search(r"(\d+)\s+days after discharge", text, re.I)
    if before or after:
        cond, key = _condition(text) if "same condition" not in lower else ("for the same condition", "post_hospitalisation_same_condition")
        return Interpretation(category=Cat.time_window, payable=True,
                              window_days_before=int(before.group(1)) if before else None,
                              window_days_after=int(after.group(1)) if after else None,
                              condition=cond, condition_key=key, **kw)
    pm = PAYABLE_RE.search(main)
    negated = bool(pm and pm.group(1)) or bool(EXCLUDED_RE.search(main))
    if negated:
        cond, key = _condition(main)
        if cond and re.search(r"\bclause\b|\bendorsement\b|\blisted\b|\bspecified\b|\bschedule\b|\bexpressly\b|\bstated\b", cond, re.I):
            cond = None
        if cond and re.match(r"(unless|except)", cond, re.I):
            return Interpretation(category=Cat.conditional_exclusion, payable=False, condition=cond, condition_key=key, **kw)
        return Interpretation(category=Cat.exclusion, payable=False, **kw)
    if pm or re.search(r"\bwill pay\b", main, re.I):
        limit = parse_limit(main)
        cond, key = _condition(main)
        if cond and re.match(r"(provided|only if|subject to the condition)", cond, re.I):
            return Interpretation(category=Cat.conditional_coverage, payable=True, condition=cond,
                                  condition_key=key, limit=limit, **kw)
        if limit:
            return Interpretation(category=Cat.limit, payable=True, limit=limit, **kw)
        return Interpretation(category=Cat.coverage, payable=True, **kw)
    if m := re.search(r"(?:INR|Rs\.?|₹)\s*[\d,]+", main) and re.search(r"limited to|maximum|up to", main, re.I):
        limit = parse_limit(main)
        if limit:
            return Interpretation(category=Cat.limit, payable=True, limit=limit, **kw)
    if re.search(r"definition", group, re.I):
        return Interpretation(category=Cat.definition, **kw)
    if re.search(r"exclusion", group + " " + heading, re.I):
        return Interpretation(category=Cat.exclusion, payable=False, **kw)
    notes.append("No recognised payable/exclusion pattern; clause kept for reference only.")
    return Interpretation(category=Cat.other, **kw)
