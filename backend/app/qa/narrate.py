"""A spoken, conversational explanation of a policy, in English or Hindi.

Instead of reading the summary list aloud, this talks the listener through it the way a friend who knows insurance
would: the good news first, then the caps, what comes out of your own pocket, the waiting periods and what isn't paid.
Every fact comes from the clauses' structured reading (the same data as the on-screen summary, which cites each
clause); nothing is invented, and only the most useful few points of each kind are spoken so it stays short.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Optional

from app.models import Clause, ClauseCategory as Cat

_ACRONYMS = {"icu": "ICU", "ct": "CT", "mri": "MRI", "opd": "OPD", "ot": "OT", "iv": "IV", "ecg": "ECG", "hiv": "HIV", "aids": "AIDS"}

_BASIS = {
    "en": {"per_day": "a day", "per_hospitalisation": "per hospital stay", "per_eye": "per eye", "per_policy_year": "a year", "per_claim": "per claim"},
    "hi": {"per_day": "रोज़", "per_hospitalisation": "हर भर्ती पर", "per_eye": "हर आँख के लिए", "per_policy_year": "हर साल", "per_claim": "हर क्लेम पर"},
}


def _term(t: str) -> str:
    return " ".join(_ACRONYMS.get(w.lower(), w) for w in t.strip().split())


def _amount(v: Optional[Decimal], lang: str) -> str:
    """Spoken rupees, Indian style: 5,000 rupees · 2 lakh rupees · 1.5 crore rupees."""
    if v is None:
        return ""
    v = Decimal(v)
    unit = "रुपये" if lang == "hi" else "rupees"
    for size, name in ((Decimal(10_000_000), "crore" if lang == "en" else "करोड़"), (Decimal(100_000), "lakh" if lang == "en" else "लाख")):
        if v >= size:
            n = (v / size).quantize(Decimal("0.1")).normalize()
            return f"{n:f} {name} {unit}"
    return f"{int(v):,} {unit}"


def _join(items: list[str], lang: str) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    # "medicines and drugs and therapy" reads badly; use "plus" when an item already contains "and"
    last = " और " if lang == "hi" else (", plus " if any(" and " in i for i in items) else " and ")
    return ", ".join(items[:-1]) + last + items[-1]


_GENERIC = re.compile(r"^(clause|section|part|article|schedule|annexure|exclusions?|benefits?|coverage|general|definitions?|other|misc)", re.I)


def _label(c: Clause) -> str:
    """How a person would name this clause's subject: its heading when that is a short, real name
    ("Diagnostic Investigations" -> "diagnostic investigations"), otherwise its first scope term."""
    h = re.sub(r"\s+", " ", c.heading or "").strip(" .:-")
    words = h.split()
    if 1 <= len(words) <= 6 and re.fullmatch(r"[A-Za-z][A-Za-z\-&,' ]+", h) and not _GENERIC.match(h):
        h = re.sub(r"\s+(expenses|cover|benefit)$", "", h, flags=re.I).replace("&", "and")
        return _term(h.lower())
    return _term(c.interpretation.scope_terms[0]) if c.interpretation.scope_terms else ""


def _first_terms(clauses: list[Clause], limit: int) -> tuple[list[str], int]:
    seen: list[str] = []
    for c in clauses:
        t = _label(c)
        if t and t.lower() not in {s.lower() for s in seen}:
            seen.append(t)
    return seen[:limit], max(0, len(seen) - limit)


def _short_title(title: str) -> str:
    """'Sahaay Secure Health Plan - Policy Wording (Version 1.0)' -> 'Sahaay Secure Health Plan'."""
    t = re.sub(r"\(.*?\)", "", title or "")
    t = re.split(r"\s+[-–—:|]\s+", t)[0]
    t = re.sub(r"(policy wording|policy document|wording|prospectus|brochure)", "", t, flags=re.I)
    t = re.sub(r"\.(pdf|png|jpe?g)$", "", t.strip(), flags=re.I).strip(" -_")
    return t or "this policy"


def narrate(clauses: list[Clause], title: str, lang: str, sum_insured=None) -> str:
    from app.qa.speech import limit_amount
    lang = "hi" if lang == "hi" else "en"
    by = lambda *cats: [c for c in clauses if c.interpretation.category in cats]  # noqa: E731
    covered, more_cov = _first_terms(by(Cat.coverage, Cat.conditional_coverage), 5)
    window = next((c.interpretation for c in by(Cat.time_window) if c.interpretation.window_days_before or c.interpretation.window_days_after), None)
    limits = [c for c in by(Cat.limit) if limit_amount(c.interpretation.limit, sum_insured) is not None]
    deductible = next((c.interpretation.amount for c in by(Cat.deductible) if c.interpretation.amount), None)
    copay = next((c.interpretation.percent for c in by(Cat.copayment) if c.interpretation.percent), None)
    waits = by(Cat.waiting_period)
    excluded, more_exc = _first_terms(by(Cat.exclusion, Cat.conditional_exclusion), 4)
    title = _short_title(title)
    B = _BASIS[lang]
    out: list[str] = []

    if lang == "en":
        out.append(f"Alright, here's your {title} in a nutshell.")
        if covered:
            out.append(f"The good news first: it pays for {_join(covered, lang)}{', and a few other things' if more_cov else ''}.")
        if window:
            out.append(f"It also covers related bills from {window.window_days_before} days before you're admitted, up to {window.window_days_after} days after you go home.")
        if limits:
            caps = [f"{_term(c.interpretation.scope_terms[0]) if c.interpretation.scope_terms else c.heading} up to {_amount(limit_amount(c.interpretation.limit, sum_insured), lang)} {B.get(c.interpretation.limit.basis, '')}".strip()
                    for c in limits[:3]]
            out.append(f"There are a few caps to keep in mind. It pays {_join(caps, lang)}{', plus a couple more on screen' if len(limits) > 3 else ''}.")
        if deductible and copay:
            out.append(f"From your own pocket, you cover the first {_amount(deductible, lang)} each year, and after that, {copay:f} percent of each claim.")
        elif deductible:
            out.append(f"From your own pocket, you cover the first {_amount(deductible, lang)} each year before the insurer starts paying.")
        elif copay:
            out.append(f"On every claim, you pay {copay:f} percent yourself.")
        if waits:
            parts = []
            for c in waits[:3]:
                it = c.interpretation
                if it.waiting_months:
                    what = _join([_term(t) for t in it.scope_terms[:2]], lang) or c.heading
                    parts.append(f"{what} only after {it.waiting_months} months")
                elif it.waiting_days:
                    parts.append(f"no illness claims in the first {it.waiting_days} days, unless it's an accident")
            out.append(f"Watch out for waiting periods: {'; '.join(parts)}.")
        if excluded:
            out.append(f"And it won't pay for things like {_join(excluded, lang)}{', among others' if more_exc else ''}.")
        out.append("That's the gist. If you want the exact wording on any point, just tap its clause number on screen.")
    else:
        out.append(f"चलिए, {title} को आसान भाषा में समझते हैं।")
        if covered:
            out.append(f"पहले अच्छी बात: इसमें {_join(covered, lang)}{' और कुछ और चीज़ों' if more_cov else ''} का खर्च मिलता है।")
        if window:
            out.append(f"भर्ती से {window.window_days_before} दिन पहले और घर जाने के {window.window_days_after} दिन बाद तक के जुड़े हुए बिल भी मिलते हैं।")
        if limits:
            caps = [f"{_term(c.interpretation.scope_terms[0]) if c.interpretation.scope_terms else c.heading} के लिए {B.get(c.interpretation.limit.basis, '')} {_amount(limit_amount(c.interpretation.limit, sum_insured), lang)} तक"
                    for c in limits[:3]]
            out.append(f"कुछ सीमाएँ ध्यान में रखिए: {_join(caps, lang)}{', और कुछ सीमाएँ स्क्रीन पर हैं' if len(limits) > 3 else ''}।")
        if deductible and copay:
            out.append(f"अपनी जेब से: हर साल पहले {_amount(deductible, lang)} आप देंगे, और उसके बाद हर क्लेम का {copay:f} प्रतिशत।")
        elif deductible:
            out.append(f"अपनी जेब से: हर साल पहले {_amount(deductible, lang)} आप देंगे, उसके बाद बीमा कंपनी भुगतान करेगी।")
        elif copay:
            out.append(f"हर क्लेम का {copay:f} प्रतिशत आपको खुद देना होगा।")
        if waits:
            parts = []
            for c in waits[:3]:
                it = c.interpretation
                if it.waiting_months:
                    what = _join([_term(t) for t in it.scope_terms[:2]], lang) or c.heading
                    parts.append(f"{what} का खर्च {it.waiting_months} महीने बाद")
                elif it.waiting_days:
                    parts.append(f"पहले {it.waiting_days} दिनों में बीमारी का क्लेम नहीं, दुर्घटना को छोड़कर")
            out.append(f"प्रतीक्षा अवधि का ध्यान रखिए: {'; '.join(parts)}।")
        if excluded:
            out.append(f"और यह {_join(excluded, lang)}{' जैसी कई' if more_exc else ' जैसी'} चीज़ों का खर्च नहीं देती।")
        out.append("बस, यही मुख्य बातें हैं। किसी भी बात का सही शब्द देखना हो, तो स्क्रीन पर धारा नंबर दबाइए।")
    return " ".join(out)
