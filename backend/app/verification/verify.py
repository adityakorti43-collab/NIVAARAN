"""Evidence verification and item-level coverage decisions.

Retrieval proposes candidate clauses; this module decides what each candidate actually establishes for a
bill item. A clause counts as evidence only when one of its own scope terms matches the item (directly,
or through the item's normalised category). Similarity scores never establish coverage.

Precedence between conflicting clauses is taken only from the documents themselves:
- an endorsement clause beginning "Notwithstanding clause X" overrides exclusion X;
- a policy precedence clause ("a specific exclusion ... prevails over general coverage") resolves a
  specific exclusion against general coverage;
- when an exclusion names the item more specifically than a coverage clause does (its matched term contains the
  coverage term, e.g. "ECG electrodes" vs "ECG"), the policy precedence clause resolves it in favour of the exclusion;
- a conditional coverage clause that names the item more specifically than a generic coverage clause (e.g. "stents" vs
  "drugs" for a drug-eluting stent) governs, so its condition is not bypassed by an incidental word match;
- anything else (e.g. two item-specific clauses that disagree) is reported as conflicting evidence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from app.models import Clause, ClaimFacts, Evidence, LimitSpec
from app.models import ClauseCategory as Cat
from app.retrieval.text import NormalizedItem, content_tokens, term_match

ITEM_LEVEL = {Cat.coverage, Cat.limit, Cat.conditional_coverage, Cat.exclusion, Cat.conditional_exclusion, Cat.time_window}
FACT_LABELS = {
    "vitamin_prescription": "Prescription by the treating doctor for the vitamin/supplement",
    "implant_invoice_submitted": "Implant invoice and barcode sticker",
    "post_hospitalisation_same_condition": "Confirmation that the expense relates to the same condition",
    "accident": "Whether the treatment arose from an accident/injury",
    "pre_existing_condition": "Whether the condition is pre-existing",
}


@dataclass
class ItemContext:
    service_date: Optional[date]
    admission_date: Optional[date]
    discharge_date: Optional[date]


def excerpt(c: Clause, limit: int = 400) -> str:
    return c.text if len(c.text) <= limit else c.text[:limit].rsplit(" ", 1)[0] + " ..."


def _ev(c: Clause, relation: str, spec: str, terms: list[str], reason: str) -> Evidence:
    return Evidence(clause_id=c.clause_id, section=c.section, heading=c.heading, document_id=c.document_id,
                    doc_type=c.doc_type, page=c.page, excerpt=excerpt(c), relation=relation, specificity=spec,
                    matched_terms=terms, reason=reason)


def _in_hospital(ctx: ItemContext) -> Optional[bool]:
    if not ctx.service_date or not ctx.admission_date:
        return None
    end = ctx.discharge_date or ctx.admission_date
    return ctx.admission_date <= ctx.service_date <= end


def verify(c: Clause, item: NormalizedItem, ctx: ItemContext) -> Evidence:
    it = c.interpretation
    matches = [(t, m) for t in it.scope_terms if (m := term_match(t, item))]
    # A pre/post-hospitalisation clause written generically ("Expenses incurred up to 15 days before admission ...")
    # covers any expense, so it is checked against every item.
    if not matches and it.category == Cat.time_window and not any(content_tokens(t) for t in it.scope_terms):
        matches = [("expenses (any item)", "general")]
    spec = "direct" if any(m == "direct" for _, m in matches) else ("general" if matches else "none")
    terms = [t for t, _ in matches]
    if it.category not in ITEM_LEVEL:
        if it.category == Cat.definition and matches:
            return _ev(c, "irrelevant", spec, terms, "Definition clause: informs interpretation but does not by itself establish coverage or exclusion.")
        return _ev(c, "inapplicable", "none", [], f"{it.category.value.replace('_', ' ').capitalize()} rule applies at claim level, not to an individual item.")
    if not matches:
        return _ev(c, "irrelevant", "none", [], "Retrieved by textual similarity, but none of this clause's covered/excluded terms "
                                                "match the item. Similarity alone is not evidence.")
    how = "names this item" if spec == "direct" else "covers the item's category"
    in_hosp = _in_hospital(ctx)
    hosp_scoped = bool(re.search(r"during hospitali[sz]ation|in-patient", c.text, re.I))
    if hosp_scoped and in_hosp is False and it.category != Cat.time_window:
        return _ev(c, "inapplicable", spec, terms, "Clause is limited to charges during hospitalisation, but this item's service "
                                                   "date is outside the admission period.")
    if it.category == Cat.time_window:
        if in_hosp is None:
            return _ev(c, "inapplicable", spec, terms, "Service or admission date missing; the pre/post-hospitalisation window cannot be checked.")
        if in_hosp:
            return _ev(c, "inapplicable", spec, terms, "Pre/post-hospitalisation clause does not apply: the item was provided during the admission.")
        if ctx.service_date < ctx.admission_date:
            gap = (ctx.admission_date - ctx.service_date).days
            ok = it.window_days_before is not None and gap <= it.window_days_before
            return _ev(c, "time_window_support" if ok else "outside_window", spec, terms,
                       f"Service {gap} day(s) before admission; pre-hospitalisation window is {it.window_days_before} days.")
        gap = (ctx.service_date - (ctx.discharge_date or ctx.admission_date)).days
        ok = it.window_days_after is not None and gap <= it.window_days_after
        return _ev(c, "time_window_support" if ok else "outside_window", spec, terms,
                   f"Service {gap} day(s) after discharge; post-hospitalisation window is {it.window_days_after} days.")
    if it.category == Cat.exclusion:
        return _ev(c, "exclusion", spec, terms, f"Exclusion clause {how} ({', '.join(terms)}).")
    if it.category == Cat.conditional_exclusion:
        return _ev(c, "conditional_exclusion", spec, terms, f"Exclusion {how} but has an exception: '{it.condition}'.")
    if it.category == Cat.conditional_coverage:
        return _ev(c, "conditional_support", spec, terms, f"Coverage {how}, conditional on: '{it.condition}'.")
    if it.overrides:
        return _ev(c, "override_support", spec, terms,
                   f"Clause {how} and expressly overrides {', '.join(it.overrides)}" + (f"; limit {it.limit.text}." if it.limit else "."))
    if it.category == Cat.limit:
        return _ev(c, "limit", spec, terms, f"Coverage clause {how}, with a limit: {it.limit.text if it.limit else ''}.")
    return _ev(c, "support", spec, terms, f"Coverage clause {how} ({', '.join(terms)}).")


@dataclass
class Decision:
    status: str  # covered | excluded | conditional | insufficient | conflict
    decisive: list[Evidence] = field(default_factory=list)
    limits: list[tuple[str, LimitSpec]] = field(default_factory=list)
    explanation: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    review: list[str] = field(default_factory=list)
    quality: str = "none"


def _overridden(exc: Evidence, overriding: list[tuple[Evidence, Clause]], clauses: dict[str, Clause]) -> Optional[Evidence]:
    target = clauses[exc.clause_id]
    for ev, oc in overriding:
        for t in oc.interpretation.overrides:
            g = target.group.lower()
            if t == target.section or (t.lower().startswith("annexure") and (g == t.lower() or g.startswith(t.lower() + " "))):
                return ev
    return None


def _weight(e: Evidence) -> int:
    """How specifically a clause names the item: matched content words, doubled when the item itself names them."""
    toks: set[str] = set()
    for t in e.matched_terms:
        toks |= set(content_tokens(t))
    return len(toks) * (2 if e.specificity == "direct" else 1)


def _contains(a: Evidence, b: Evidence) -> bool:
    """Every term b matched is strictly part of a longer term a matched (e.g. 'ecg' within 'ecg electrodes')."""
    at = [set(content_tokens(t)) for t in a.matched_terms]
    bt = [set(content_tokens(t)) for t in b.matched_terms]
    return bool(bt) and all(any(x and x < y for y in at) for x in bt)


def decide(evidence: list[Evidence], clauses: dict[str, Clause], facts: ClaimFacts,
           precedence: Optional[Clause]) -> Decision:
    by = lambda *rels: [e for e in evidence if e.relation in rels]
    sup = by("support", "limit", "override_support", "time_window_support")
    csup = by("conditional_support")
    exc = by("exclusion")
    cexc = by("conditional_exclusion")
    d = Decision(status="insufficient")
    if not evidence:
        d.quality = "none"
    elif not (sup or csup or exc or cexc):
        d.quality = "weak"

    overriding = [(e, clauses[e.clause_id]) for e in by("override_support")]
    kept_exc = []
    for e in exc:
        ov = _overridden(e, overriding, clauses)
        if ov:
            d.explanation.append(f"Exclusion {e.section} does not apply: {ov.section} begins 'Notwithstanding' and expressly overrides it.")
        else:
            kept_exc.append(e)
    exc = kept_exc

    def limits_of(evs: list[Evidence]):
        for e in evs:
            lim = clauses[e.clause_id].interpretation.limit
            if lim and (lim.amount is not None or lim.percent_of_sum_insured is not None):
                d.limits.append((e.clause_id, lim))

    def fact_value(key: Optional[str]) -> str:
        return getattr(facts, key) if key and hasattr(facts, key) else "unknown"

    if exc:
        direct_exc = [e for e in exc if e.specificity == "direct"]
        direct_sup = [e for e in sup if e.specificity == "direct"]
        if direct_exc and direct_sup and precedence is not None and all(any(_contains(e, s) for e in direct_exc) for s in direct_sup):
            d.status, d.decisive = "excluded", direct_exc + [_ev(precedence, "precedence", "none", [], "Policy precedence rule.")]
            d.explanation.append(
                f"Exclusion {', '.join(e.section for e in direct_exc)} names this item more specifically "
                f"({', '.join(t for e in direct_exc for t in e.matched_terms)}) than coverage {', '.join(e.section for e in direct_sup)} "
                f"({', '.join(t for e in direct_sup for t in e.matched_terms)}); under precedence clause {precedence.section} the specific exclusion prevails.")
            d.quality = "direct"
        elif direct_exc and direct_sup:
            d.status, d.decisive = "conflict", direct_exc + direct_sup
            d.explanation.append(
                f"Item-specific clauses disagree: {', '.join(e.section for e in direct_sup)} states it is payable while "
                f"{', '.join(e.section for e in direct_exc)} states it is not payable. The documents do not establish which prevails.")
            d.review.append("Conflicting item-specific clauses")
            d.quality = "direct"
        elif direct_exc:
            if sup and precedence is not None:
                d.status, d.decisive = "excluded", direct_exc + [_ev(precedence, "precedence", "none", [], "Policy precedence rule.")]
                d.explanation.append(
                    f"Specific exclusion {', '.join(e.section for e in direct_exc)} applies; general coverage "
                    f"{', '.join(e.section for e in sup)} is overridden under precedence clause {precedence.section}.")
            elif sup:
                d.status, d.decisive = "conflict", direct_exc + sup
                d.explanation.append("A specific exclusion and general coverage both apply and the policy states no precedence rule.")
                d.review.append("No documented precedence between exclusion and coverage")
            else:
                d.status, d.decisive = "excluded", direct_exc
                d.explanation.append(f"Exclusion {', '.join(e.section for e in direct_exc)} names this item.")
            d.quality = "direct"
        else:
            if sup:
                d.status, d.decisive = "conflict", exc + sup
                d.explanation.append("Category-level exclusion and coverage clauses both apply; the documents do not resolve which prevails.")
                d.review.append("Category-level conflict")
            else:
                d.status, d.decisive = "excluded", exc
                d.explanation.append(f"Exclusion {', '.join(e.section for e in exc)} covers this item's category.")
            d.quality = "general"
        return d

    if cexc:
        e = cexc[0]
        c = clauses[e.clause_id].interpretation
        v = fact_value(c.condition_key)
        label = FACT_LABELS.get(c.condition_key or "", c.condition or "Condition stated in the clause")
        if v == "yes":
            if sup:
                d.status, d.decisive = "covered", [e] + sup
                d.explanation.append(f"Exclusion {e.section} has an exception ('{c.condition}') which the claim facts state is met; "
                                     f"coverage under {', '.join(s.section for s in sup)}.")
                limits_of(sup)
            else:
                d.status, d.decisive = "insufficient", [e]
                d.explanation.append(f"The exception in {e.section} is met, but no clause establishes positive coverage for this item.")
                d.review.append("No positive coverage clause")
        elif v == "no":
            d.status, d.decisive = "excluded", [e]
            d.explanation.append(f"Exclusion {e.section} applies and the claim facts state its exception is not met.")
        else:
            d.status, d.decisive = "conditional", [e] + sup
            d.explanation.append(f"Exclusion {e.section} applies {c.condition}. Whether the exception is met is not established.")
            d.missing.append(f"{label} (clause {e.section})")
            d.review.append("Exception to exclusion not established")
        d.quality = e.specificity
        return d

    if sup and csup and max(_weight(e) for e in csup) > max(_weight(e) for e in sup):
        best = max(csup, key=_weight)
        d.explanation.append(f"{best.section} names this item more specifically ({', '.join(best.matched_terms)}) than "
                             f"{', '.join(e.section for e in sup)} ({', '.join(t for e in sup for t in e.matched_terms)}), so its condition governs.")
        sup, csup = [], [best]

    if sup:
        tw = [e for e in sup if e.relation == "time_window_support"]
        if tw and len(tw) == len(sup):
            c = clauses[tw[0].clause_id].interpretation
            v = fact_value(c.condition_key)
            if v != "yes":
                d.status, d.decisive = "conditional", tw
                d.explanation.append(f"Post/pre-hospitalisation cover under {tw[0].section} requires that the expense is {c.condition}.")
                d.missing.append(f"{FACT_LABELS.get(c.condition_key or '', c.condition)} (clause {tw[0].section})")
                d.review.append("Time-window condition not established")
                d.quality = tw[0].specificity
                return d
        d.status, d.decisive = "covered", sup
        d.explanation.append("Payable under " + ", ".join(f"{e.section} ({e.heading})" for e in sup) + ".")
        limits_of(sup)
        d.quality = "direct" if any(e.specificity == "direct" for e in sup) else "general"
        return d

    if csup:
        e = csup[0]
        c = clauses[e.clause_id].interpretation
        v = fact_value(c.condition_key)
        if v == "yes":
            d.status, d.decisive = "covered", [e]
            d.explanation.append(f"Payable under {e.section}; the claim facts state its condition is met.")
            limits_of([e])
        else:
            d.status, d.decisive = "conditional", [e]
            d.explanation.append(f"Payable under {e.section} only {c.condition}; this is {'stated as not met' if v == 'no' else 'not established'}.")
            d.missing.append(f"{FACT_LABELS.get(c.condition_key or '', c.condition)} (clause {e.section})")
            d.review.append("Coverage condition not established")
        d.quality = e.specificity
        return d

    ow = by("outside_window")
    if ow:
        d.status, d.decisive = "excluded", ow[:1]
        d.explanation.append(f"{ow[0].reason} It falls outside the window in {ow[0].section}, and no other clause covers it.")
        d.quality = ow[0].specificity
        return d

    d.status = "insufficient"
    d.explanation.append("No retrieved clause establishes coverage or exclusion for this item. The documents provided do not "
                         "answer this; it is not assumed covered or excluded.")
    d.missing.append("A policy clause addressing this charge")
    d.review.append("Insufficient evidence")
    return d
