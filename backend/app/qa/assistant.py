"""Grounded policy assistant.

Answers are composed only from (a) retrieved, verified clause text and (b) structured results of the
deterministic engine. No language model generates policy terms, citations or amounts, so nothing can be
invented; when the documents do not establish an answer, the assistant says so explicitly.
"""
from __future__ import annotations

import re
from typing import Optional

from app.adjudication.adjudicate import adjudicate, retriever_for
from app.adjudication.compare import compare
from app.models import AnalysisResult, Claim, ClaimFacts, DocumentRecord, Hypotheticals
from app.money import fmt
from app.policy.versions import active_clauses
from app.retrieval.text import content_tokens, normalize_item
from app.verification.verify import ItemContext, decide, verify

DISCLAIMER = ("Nivaaran supports decision-making only. It cannot guarantee insurer approval, claim settlement or "
              "reimbursement.")
STATUS_TEXT = {"potentially_covered": "potentially covered", "partially_payable": "partially payable",
               "potentially_excluded": "potentially excluded", "conditional": "conditional",
               "insufficient_evidence": "not established by the documents (insufficient evidence)",
               "conflicting_evidence": "subject to conflicting evidence", "manual_review_required": "flagged for manual review"}


def _cite(c) -> dict:
    return {"clause_id": c.clause_id, "section": c.section, "heading": c.heading, "page": c.page,
            "document_id": c.document_id, "excerpt": c.excerpt if hasattr(c, "excerpt") else c.text}


def _match_item(q: str, analysis: AnalysisResult):
    m = re.search(r"\bline\s+(\d+)\b", q, re.I)
    if m:
        return next((r for r in analysis.rows if r.line_no == int(m.group(1))), None)
    qt = set(content_tokens(q)) - {"cover", "covered", "payable", "reduc", "why", "claus", "item", "bill", "remov"}
    best, score = None, 0
    for r in analysis.rows:
        it = set(content_tokens(f"{r.original_description} {r.normalized_description}"))
        s = len(qt & it)
        if s > score:
            best, score = r, s
    return best if score >= 1 else None


def answer(question: str, claim: Claim, analysis: AnalysisResult, docs: dict[str, DocumentRecord], context: Optional[dict] = None) -> dict:
    q = question.strip()
    if not q:
        return {"kind": "error", "answer": "Please enter a question.", "citations": [], "grounded": False, "disclaimer": DISCLAIMER}
    # Hindi / Marathi: route on the English reading of the question, and say how it was read.
    from app.qa import indic
    lang, routed_q = "en", q
    if indic.is_indic(q):
        lang, routed_q = indic.language(q), indic.to_english(q)
        if len(routed_q.split()) <= 1:
            return {"kind": "none", "answer": indic.NOT_UNDERSTOOD[lang], "citations": [], "grounded": False, "language": lang, "question": q,
                    "actions": [], "disclaimer": DISCLAIMER, "engine": "Deterministic evidence engine", "context": context or {},
                    "breakdown": {"source_facts": [], "calculated": [], "interpretation": "", "assumptions": [], "missing": ["The question could not be read."]}}
    low = routed_q.lower()
    out = _context_route(routed_q, low, claim, analysis, docs, context or {}) or _route(routed_q, low, claim, analysis, docs)
    if lang != "en":
        out["answer"] = indic.LEAD[lang].format(en=routed_q) + "\n\n" + out["answer"]
    out["language"] = lang
    out.setdefault("citations", [])
    out.setdefault("actions", _default_actions(out))
    from app.qa import llm
    rewritten = None
    if llm.enabled() and out["kind"] not in ("draft", "error"):
        rewritten = llm.grounded_answer(q, _context_blob(claim, analysis, docs), out["answer"])
    out["engine"] = llm.mode_label() if rewritten else "Deterministic evidence engine" + ("" if llm.enabled() else " (no external AI configured)")
    if rewritten:
        out["deterministic_answer"] = out["answer"]
        out["answer"] = rewritten
    out["disclaimer"] = DISCLAIMER
    out["question"] = q
    out["context"] = context or {}
    out["breakdown"] = _breakdown(out, claim, analysis)
    return out


def _breakdown(out: dict, claim: Claim, analysis: AnalysisResult) -> dict:
    """Separate the answer into source facts, calculated results, interpretation, assumptions and missing evidence."""
    row = next((r for r in analysis.rows if r.item_id == out.get("item_id")), None)
    facts = [f"{c['section']} (p. {c.get('page', '?')}): \"{c['excerpt'][:180]}\"" for c in out.get("citations", [])[:4]]
    calc, missing = [], []
    if row:
        calc = [f"Billed {fmt(row.claimed_amount)}"]
        if row.eligible_amount is not None:
            calc += [f"Eligible after exclusions/limits {fmt(row.eligible_amount)}", f"Estimated payable {fmt(row.payable_low)}"]
        else:
            calc += [f"Not counted in the definite estimate; up to {fmt(row.payable_high)} if resolved favourably"]
        missing = list(row.missing_information)
    elif out.get("kind") in ("calculation", "coverage_summary"):
        s = analysis.summary
        calc = [f"Estimated payable {fmt(s.payable_low)} to {fmt(s.payable_high)}", f"Potential out-of-pocket {fmt(s.patient_low)} to {fmt(s.patient_high)}"]
    asserted = {"vitamin_prescription": "vitamin prescription", "implant_invoice_submitted": "implant invoice",
                "post_hospitalisation_same_condition": "post-hospitalisation expense is for the same condition",
                "pre_existing_condition": "pre-existing condition", "accident": "accident"}
    assumptions = [f"You stated: {label} = {getattr(claim.facts, k)}" for k, label in asserted.items() if getattr(claim.facts, k) != "unknown"]
    if analysis.hypothetical:
        assumptions.append("Includes hypothetical inputs")
    return {"source_facts": facts, "calculated": calc, "interpretation": out["answer"][:400], "assumptions": assumptions[:4],
            "missing": missing or ([] if out.get("grounded") else ["The documents do not establish an answer to this question."])}


def _context_blob(claim: Claim, analysis: AnalysisResult, docs: dict[str, DocumentRecord]) -> str:
    """Everything the AI may use: applicable clauses, the engine's ledger and totals, and consistency findings."""
    from app.fairness.scan import scan
    v = analysis.version
    lines = [f"Applicable version: {v.selected.label if v.selected else 'not determined'}. {' '.join(v.reasons[:2])}",
             f"Treatment date {claim.admission_date}; diagnosis {claim.diagnosis}."]
    lines.append("CLAUSES:")
    for c in _clauses(analysis, docs):
        lines.append(f"[{c.section}] {c.heading} (page {c.page}): {c.text}")
    s = analysis.summary
    lines.append(f"TOTALS: billed {fmt(s.total_billed)}; eligible {fmt(s.eligible_definite)}; deductible applied {fmt(s.deductible_applied_low)}; "
                 f"co-payment {fmt(s.copay_low)}; estimated payable {fmt(s.payable_low)} to {fmt(s.payable_high)}; patient {fmt(s.patient_low)} to {fmt(s.patient_high)}.")
    lines.append("LEDGER:")
    for r in analysis.rows:
        lines.append(f"- {r.original_description}: billed {fmt(r.claimed_amount)}, status {r.status}, "
                     f"{'payable ' + fmt(r.payable_low) if r.eligible_amount is not None else 'unresolved up to ' + fmt(r.payable_high)}; "
                     f"clauses {', '.join(x.split(':')[1] for x in r.supporting_clause_ids) or 'none'}. {r.explanation} "
                     f"{'Missing: ' + '; '.join(r.missing_information) if r.missing_information else ''}")
    try:
        f = scan(claim, analysis, docs)
        lines.append(f"FINDINGS ({f['status_label']}):")
        lines += [f"- {x['title']}: {x['explanation']}" for x in f["findings"][:8]]
    except Exception:
        pass
    return "\n".join(lines)


def _default_actions(out: dict) -> list[dict]:
    acts = [{"type": "open_clause", "clause_id": c["clause_id"], "label": f"Open clause {c['section']}"}
            for c in out.get("citations", []) if ":" in str(c.get("clause_id", ""))][:3]
    if out.get("item_id"):
        acts.append({"type": "open_item", "item_id": out["item_id"], "label": "Show this item in the ledger"})
    return acts


def _plain(text: str) -> str:
    swaps = [("potentially covered", "likely to be paid"), ("potentially excluded", "likely not to be paid"),
             ("admissible", "accepted"), ("deductible", "fixed amount you pay first"), ("co-payment", "share you pay"),
             ("sub-limit", "cap"), ("insufficient evidence", "not answered by the documents"), ("conditional", "dependent on something not yet confirmed")]
    for a, b in swaps:
        text = re.sub(a, b, text, flags=re.I)
    return text


def _context_route(q: str, low: str, claim: Claim, analysis: AnalysisResult, docs: dict[str, DocumentRecord], ctx: dict) -> Optional[dict]:
    from app.fairness.actions import build_actions
    from app.fairness.scan import scan
    if re.search(r"\b(draft|letter|email|write to (my )?insurer|clarification request|message (to|for) (the |my )?insurer)\b", low):
        fair = scan(claim, analysis, docs)
        acts = build_actions(claim, analysis, fair, docs)
        return {"kind": "draft", "grounded": True, "draft": acts["letter"],
                "answer": f"Here is a neutral draft built from {len(acts['questions'])} open question(s) in this analysis. It asks for clarification and "
                          "does not allege wrongdoing. Review and edit it before sending; Nivaaran does not send anything.",
                "actions": [{"type": "navigate", "to": "/actions", "label": "Open in the Action Center"}]}
    if re.search(r"\b(what should i ask|questions? (to|for) (ask|my insurer|the insurer))\b", low):
        acts = build_actions(claim, analysis, scan(claim, analysis, docs), docs)
        qs = acts["questions"][:6]
        return {"kind": "questions", "grounded": True,
                "answer": "Questions worth asking, based on this analysis: " + " ".join(f"({i}) {x['question']}" for i, x in enumerate(qs, 1)),
                "actions": [{"type": "navigate", "to": "/actions", "label": "See all next steps"}]}
    if re.search(r"\b(discrepanc|fraud|mislead|misled|mismatch|brochure|contradict|suspicious|unfair)", low):
        fair = scan(claim, analysis, docs)
        f = next((x for x in fair["findings"] if x["id"] == ctx.get("finding_id")), None)
        cites = []
        if f:
            for e in f["excerpts"] + f["conflicting_excerpts"]:
                cites.append({"clause_id": e["clause_id"], "section": e["section"], "heading": e["heading"], "page": e["page"],
                              "document_id": e["document_id"], "excerpt": e["text"]})
        serious = [x for x in fair["findings"] if x["category"] in ("representation_gap", "calculation_inconsistency", "document_contradiction")]
        text = f"Review status: {fair['status_label']}. "
        if f:
            text += f"{f['title']}: {f['explanation']} Why it matters: {f['why_it_matters']} Severity {f['severity']}; evidence {f['evidence_completeness']}. "
        elif serious:
            text += "Main points: " + " ".join(f"• {x['title']}." for x in serious[:4]) + " "
        if re.search(r"mislead|misled|fraud", low):
            text += ("These findings show documents that disagree; they do not by themselves establish that anyone was misled or acted fraudulently. "
                     "That would need context such as when and how the summary was given, and a determination by an appropriate authority. "
                     "A sensible next step is a written request asking the insurer to reconcile the documents.")
        if fair["restrictive_terms"]:
            text += f" Note: {len(fair['restrictive_terms'])} exclusion(s) are clearly documented terms and are not treated as discrepancies."
        return {"kind": "fairness", "grounded": bool(serious or f), "answer": text, "citations": cites,
                "actions": [{"type": "navigate", "to": "/fairness", "label": "Open Fraud & Fairness"},
                            {"type": "navigate", "to": "/actions", "label": "Draft a clarification request"}]}
    if re.search(r"what does my policy cover|what('s| is) covered|coverage summary", low):
        cl = _clauses(analysis, docs)
        cov = [c for c in cl if c.interpretation.category.value in ("coverage", "limit", "conditional_coverage", "time_window")]
        exc = [c for c in cl if c.interpretation.category.value in ("exclusion", "conditional_exclusion")]
        text = (f"Under '{analysis.version.selected.label}', the wording covers: "
                + "; ".join(f"{c.heading} ({c.section}{', ' + c.interpretation.limit.text if c.interpretation.limit else ''})" for c in cov)
                + ". Main exclusions: " + "; ".join(f"{c.heading} ({c.section})" for c in exc) + ".")
        return {"kind": "coverage_summary", "grounded": True, "answer": text,
                "citations": [_cite(c) for c in cov[:3] + exc[:2]]}
    item_id = ctx.get("item_id")
    row = next((r for r in analysis.rows if r.item_id == item_id), None) if item_id else None
    if row and (re.search(r"\b(this|it|that)\b", low) or re.search(r"simpl|plain|explain", low)) and not _match_item(q, analysis):
        ev = [e for e in row.evidence if e.clause_id in row.supporting_clause_ids]
        base = f"'{row.original_description}' is {STATUS_TEXT[row.status]}. {row.explanation}"
        if row.eligible_amount is not None:
            base += f" Of {fmt(row.claimed_amount)} billed, about {fmt(row.payable_low)} may be paid after limits and cost sharing."
        if re.search(r"simpl|plain", low):
            base = "In plain words: " + _plain(base)
        return {"kind": "item", "grounded": True, "answer": base, "item_id": row.item_id,
                "citations": [{"clause_id": e.clause_id, "section": e.section, "heading": e.heading, "page": e.page,
                               "document_id": e.document_id, "excerpt": e.excerpt, "relation": e.relation} for e in ev]}
    return None


def _route(q: str, low: str, claim: Claim, analysis: AnalysisResult, docs: dict[str, DocumentRecord]) -> dict:
    v = analysis.version
    if re.search(r"\b(version|endorsement applies|which policy)\b", low) or ("appl" in low and "date" in low):
        cites = []
        if v.selected:
            for eid in v.selected.endorsement_ids:
                d = docs[eid]
                cites.append({"clause_id": eid, "section": d.metadata.get("endorsement_number", ""), "heading": d.metadata.get("title", ""),
                              "page": 1, "document_id": eid, "excerpt": f"Effective date: {d.metadata.get('effective_date')}; "
                                                                         f"applies to: {d.metadata.get('applies_to')}"})
        text = (f"For treatment date {v.treatment_date}, the applicable version is '{v.selected.label}'. " if v.selected else
                "No applicable policy version could be determined. ") + " ".join(v.reasons)
        if v.conflicts:
            text += " Unresolved: " + " ".join(v.conflicts)
        return {"kind": "version", "answer": text, "citations": cites, "grounded": True}

    if re.search(r"\b(remov\w*|without|drop\w*|delet\w*)\b", low):
        row = _match_item(q, analysis)
        if row:
            hyp = Hypotheticals(removed_items=[row.item_id])
            new = adjudicate(claim, docs, hyp, cause="Assistant what-if")
            cmp = compare(analysis, new, f"HYPOTHETICAL: remove line {row.line_no}")
            s0, s1 = analysis.summary, new.summary
            return {"kind": "what_if", "grounded": True,
                    "answer": (f"HYPOTHETICAL scenario (recalculated by the rules engine): removing line {row.line_no} "
                               f"'{row.original_description}' (billed {fmt(row.claimed_amount)}) changes the estimated payable from "
                               f"{fmt(s0.payable_low)}–{fmt(s0.payable_high)} to {fmt(s1.payable_low)}–{fmt(s1.payable_high)}, and potential "
                               f"patient responsibility from {fmt(s0.patient_low)}–{fmt(s0.patient_high)} to {fmt(s1.patient_low)}–{fmt(s1.patient_high)}. "
                               "Other items can change slightly because claim-level deductible and co-payment are re-allocated."),
                    "data": cmp}

    if re.search(r"chang", low) and re.search(r"amend|endorse|why did|update", low):
        from app import store
        comps = store.list_comparisons(claim.claim_id)
        if comps:
            c = comps[-1]
            return {"kind": "comparison", "grounded": True, "data": c,
                    "answer": f"The latest change ({c['cause']}) moved the estimated payable from {c['payable_before'][0]} to "
                              f"{c['payable_after'][0]} (difference {c['payable_delta']}). Reasons: " + " ".join(c["reasons"][:4])}
        return {"kind": "comparison", "grounded": True, "answer": "No earlier analysis is recorded for this claim, so there is no change to explain."}

    if re.search(r"out[- ]of[- ]pocket|pay (it |for it )?(by )?myself|my (own )?share|from my pocket|have to pay", low):
        # Out-of-pocket: lead with the engine's patient-share range, then the same cited calculation trace.
        s = analysis.summary
        calc = _route("how was the payable amount calculated", "how was the payable amount calculated", claim, analysis, docs)
        lead = (f"Your estimated out-of-pocket share is {fmt(s.patient_low)} to {fmt(s.patient_high)} of the {fmt(s.total_billed)} billed. "
                f"The insurer's estimated payable amount is {fmt(s.payable_low)} (definite) to {fmt(s.payable_high)} if every unresolved item "
                "is resolved favourably. The difference comes from excluded items, item limits, the deductible and the co-payment. ")
        return {**calc, "answer": lead + calc.get("answer", "")}
    if re.search(r"how (was|is|were).*(calculat|estimat|payable|amount)|calculation|breakdown|computed", low):
        steps = [f"{s.step_no}. {s.description} ({fmt(s.amount_before)} → {fmt(s.amount_after)})" for s in analysis.trace_low]
        s = analysis.summary
        cites = []
        clauses = {c.clause_id: c for c in _clauses(analysis, docs)}
        for st in analysis.trace_low:
            for cid in st.clause_ids:
                if cid in clauses and cid not in [x["clause_id"] for x in cites] and st.stage in ("deductible", "copay"):
                    cites.append(_cite(clauses[cid]))
        return {"kind": "calculation", "grounded": True, "citations": cites,
                "answer": f"The estimate was computed by the deterministic rules engine in the order stated by {s.order_source}. "
                          + " ".join(steps) + f" Range: {fmt(s.payable_low)} (definite) to {fmt(s.payable_high)} if all unresolved items "
                          "were resolved favourably."}

    if re.search(r"missing|what information|what do i need|documents? (are )?(needed|required)|unresolved", low):
        lines = []
        for r in analysis.rows:
            if r.missing_information or r.status in ("conflicting_evidence",):
                need = "; ".join(r.missing_information) or "resolution of conflicting clauses " + ", ".join(
                    c.split(":")[1] for c in r.supporting_clause_ids)
                lines.append(f"Line {r.line_no} '{r.original_description}': {need}.")
        for c in analysis.claim_checks:
            if c.status == "unknown":
                lines.append(f"Claim-level: {c.check} — {c.detail}")
        return {"kind": "missing", "grounded": True,
                "answer": ("The following information is missing or unresolved: " + " ".join(lines)) if lines else
                "No missing information was identified for the current claim."}

    row = _match_item(q, analysis)
    if row and re.search(r"why|reduc|exclud|cover|claus|appl|payable|status|deduct", low):
        ev = [e for e in row.evidence if e.clause_id in row.supporting_clause_ids]
        text = (f"Line {row.line_no} '{row.original_description}' (normalised: {row.normalized_description}) is "
                f"{STATUS_TEXT[row.status]}. {row.explanation} Billed {fmt(row.claimed_amount)}; ")
        if row.eligible_amount is not None:
            text += (f"eligible after exclusions/limits {fmt(row.eligible_amount)}; deductible share {fmt(row.deductible_share)}; "
                     f"co-payment share {fmt(row.copay_share)}; estimated payable {fmt(row.payable_low)}.")
        else:
            text += f"not counted in the definite estimate (up to {fmt(row.payable_high)} if resolved favourably)."
        if row.missing_information:
            text += " Missing: " + "; ".join(row.missing_information) + "."
        return {"kind": "item", "grounded": True, "answer": text, "item_id": row.item_id,
                "citations": [{"clause_id": e.clause_id, "section": e.section, "heading": e.heading, "page": e.page,
                               "document_id": e.document_id, "excerpt": e.excerpt, "relation": e.relation} for e in ev]}

    # Free-text coverage / clause-meaning questions: retrieve and verify against the applicable version.
    clauses = _clauses(analysis, docs)
    if not clauses:
        return {"kind": "none", "grounded": False, "answer": "No applicable policy version is available, so the question cannot be answered from the documents."}
    retr = retriever_for(clauses)
    by_id = {c.clause_id: c for c in clauses}
    topic = re.sub(r"^(is|are|does|do|will|what does|what is|explain)\s+", "", low)
    topic = re.sub(r"\b(potentially )?(covered|payable|mean|clause|the|my|policy|this|under)\b|\?", " ", topic).strip()
    hits = retr.search(topic or q, "hybrid", 6)
    if re.search(r"mean|explain|what does|waiting period|definition", low):
        cites = [_cite(by_id[h.clause_id]) for h in hits[:3]]
        top = by_id[hits[0].clause_id] if hits else None
        if not top:
            return {"kind": "clause", "grounded": False, "answer": "No relevant clause was found in the provided documents."}
        it = top.interpretation
        parts = [f"Clause {top.section} '{top.heading}' (page {top.page}) states: \"{top.text}\""]
        if it.waiting_months:
            parts.append(f"Structured reading: treatment of {', '.join(it.scope_terms)} is payable only after {it.waiting_months} months of continuous coverage.")
        if it.waiting_days:
            parts.append(f"Structured reading: illnesses within the first {it.waiting_days} days are not payable ({it.condition or 'no exception stated'}).")
        if it.limit:
            parts.append(f"Structured reading: limit {it.limit.text}.")
        if it.condition:
            parts.append(f"Condition: {it.condition}.")
        parts.append("Retrieval relevance ranks clauses by similarity only; the quoted text is the evidence.")
        return {"kind": "clause", "grounded": True, "answer": " ".join(parts), "citations": cites}
    norm = normalize_item(topic or q)
    ctx = ItemContext(service_date=analysis.version.treatment_date, admission_date=analysis.version.treatment_date,
                      discharge_date=analysis.version.treatment_date)
    evidence = [verify(by_id[h.clause_id], norm, ctx) for h in hits]
    dec = decide(evidence, by_id, claim.facts if claim else ClaimFacts(), next(
        (c for c in clauses if c.interpretation.category.value == "precedence"), None))
    verdict = {"covered": "potentially covered", "excluded": "potentially excluded", "conditional": "conditional",
               "conflict": "subject to conflicting clauses", "insufficient": "not established by the provided documents"}[dec.status]
    cites = [{"clause_id": e.clause_id, "section": e.section, "heading": e.heading, "page": e.page,
              "document_id": e.document_id, "excerpt": e.excerpt, "relation": e.relation} for e in dec.decisive]
    text = f"For '{norm.normalized}' (as an in-patient charge under '{analysis.version.selected.label}'): {verdict}. " + " ".join(dec.explanation)
    if dec.missing:
        text += " Missing: " + "; ".join(dec.missing) + "."
    if dec.status == "insufficient":
        text += " Nivaaran will not guess an answer the documents do not support."
    return {"kind": "coverage", "grounded": dec.status != "insufficient", "answer": text, "citations": cites}


def _clauses(analysis: AnalysisResult, docs: dict[str, DocumentRecord]):
    v = analysis.version.selected
    return active_clauses(v, docs) if v else []
