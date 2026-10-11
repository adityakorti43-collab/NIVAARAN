"""Integrated adjudication: version selection -> retrieval -> verification -> deterministic engine -> ledger."""
from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from app.engine.calc import DEFAULT_ORDER, EngineItem, EngineParams, check_invariants, run
from app.models import (NOT_FOUND, AnalysisResult, BillItem, Claim, ClaimCheck, Clause, DocumentRecord, Evidence,
                        FinancialSummary, Hypotheticals, LedgerRow, PolicyVersion, VersionSelection)
from app.models import ClauseCategory as Cat
from app.money import ZERO, fmt, money, q
from app.policy.versions import active_clauses, build_versions, select_version
from app.retrieval.retrievers import Retriever
from app.retrieval.text import CATEGORY_LABELS, content_tokens, normalize_item
from app.verification.verify import ItemContext, decide, verify

_RETRIEVERS: dict[str, Retriever] = {}
CANDIDATES_PER_METHOD = 8


def retriever_for(clauses: list[Clause]) -> Retriever:
    key = hashlib.sha1("|".join(sorted(c.clause_id + c.text for c in clauses)).encode()).hexdigest()
    if key not in _RETRIEVERS:
        _RETRIEVERS[key] = Retriever(clauses)
    return _RETRIEVERS[key]


def _first(clauses: list[Clause], cat: Cat) -> Optional[Clause]:
    return next((c for c in clauses if c.interpretation.category == cat), None)


def _shift(d: Optional[date], delta: timedelta) -> Optional[date]:
    return d + delta if d else None


def apply_hypotheticals(claim: Claim, hyp: Optional[Hypotheticals]) -> tuple[list[BillItem], date, Optional[date], list[str]]:
    notes: list[str] = []
    items = [i.model_copy() for i in claim.bill.items]
    adm, dis = claim.admission_date, claim.discharge_date
    if not hyp:
        return items, adm, dis, notes
    if hyp.treatment_date and hyp.treatment_date != adm:
        delta = hyp.treatment_date - adm
        adm, dis = hyp.treatment_date, _shift(dis, delta)
        for i in items:
            i.service_date = _shift(i.service_date, delta)
        notes.append(f"HYPOTHETICAL treatment date {adm} (all bill dates shifted by {delta.days} days).")
    kept = []
    for i in items:
        if i.item_id in hyp.removed_items:
            notes.append(f"HYPOTHETICAL: removed '{i.description}'.")
            continue
        if i.item_id in hyp.item_quantities:
            i.quantity = Decimal(hyp.item_quantities[i.item_id])
            if i.unit_price is not None and i.item_id not in hyp.item_amounts:
                i.amount = q(i.unit_price * i.quantity)
            notes.append(f"HYPOTHETICAL: quantity of '{i.description}' set to {i.quantity}.")
        if i.item_id in hyp.item_amounts:
            i.amount = money(str(hyp.item_amounts[i.item_id]))
            notes.append(f"HYPOTHETICAL: amount of '{i.description}' set to {fmt(i.amount)}.")
        kept.append(i)
    for j, a in enumerate(hyp.added_items, start=1):
        a = a.model_copy(update={"item_id": a.item_id or f"H{j:02d}", "line_no": 900 + j})
        kept.append(a)
        notes.append(f"HYPOTHETICAL: added '{a.description}' ({fmt(a.amount)}).")
    return kept, adm, dis, notes


def claim_checks(clauses: list[Clause], claim: Claim, policy: DocumentRecord, adm: date) -> list[ClaimCheck]:
    checks: list[ClaimCheck] = []
    since_raw = policy.metadata.get("continuous_coverage_since", NOT_FOUND)
    since = date.fromisoformat(since_raw) if since_raw != NOT_FOUND else None
    diag_tokens = set(content_tokens(f"{claim.diagnosis} {claim.title}"))
    for c in clauses:
        it = c.interpretation
        if it.category != Cat.waiting_period:
            continue
        if it.condition_key == "pre_existing_condition":
            v = claim.facts.pre_existing_condition
            if v == "no":
                checks.append(ClaimCheck(check=c.heading, status="not_applicable", clause_ids=[c.clause_id],
                                         detail="Claim facts state the condition is not pre-existing (user-asserted)."))
                continue
            if v == "unknown":
                checks.append(ClaimCheck(check=c.heading, status="unknown", clause_ids=[c.clause_id],
                                         detail="Whether the condition is pre-existing is not established."))
                continue
        elif it.waiting_months:
            hits = [t for t in it.scope_terms if set(content_tokens(t)) & diag_tokens]
            if not hits:
                checks.append(ClaimCheck(check=c.heading, status="not_applicable", clause_ids=[c.clause_id],
                                         detail=f"Diagnosis '{claim.diagnosis}' is not among the listed conditions ({', '.join(it.scope_terms)})."))
                continue
        if it.waiting_days and claim.facts.accident == "yes":
            checks.append(ClaimCheck(check=c.heading, status="not_applicable", clause_ids=[c.clause_id],
                                     detail="Accident exception stated in the claim facts."))
            continue
        if not since:
            checks.append(ClaimCheck(check=c.heading, status="unknown", clause_ids=[c.clause_id],
                                     detail="Continuous-coverage start date not found in the provided documents."))
            continue
        if it.waiting_days:
            ok = (adm - since).days >= it.waiting_days
            detail = f"Coverage since {since}; admission {adm} is {(adm - since).days} days later (waiting period {it.waiting_days} days)."
        else:
            months = (adm.year - since.year) * 12 + adm.month - since.month - (1 if adm.day < since.day else 0)
            ok = months >= (it.waiting_months or 0)
            detail = f"Coverage since {since}; {months} completed months at admission (required {it.waiting_months})."
        checks.append(ClaimCheck(check=c.heading, status="satisfied" if ok else "not_satisfied", clause_ids=[c.clause_id], detail=detail))
    return checks


STATUS_MAP = {"covered": "potentially_covered", "excluded": "potentially_excluded", "conditional": "conditional",
              "insufficient": "insufficient_evidence", "conflict": "conflicting_evidence"}


def adjudicate(claim: Claim, docs: dict[str, DocumentRecord], hyp: Optional[Hypotheticals] = None,
               cause: str = "Analysis requested") -> AnalysisResult:
    hyp = hyp if hyp and not hyp.is_empty() else None
    policy = docs[claim.policy_document_id]
    endorsements = [docs[e] for e in claim.endorsement_ids if e in docs]
    items, adm, dis, hyp_notes = apply_hypotheticals(claim, hyp)
    versions, conflicts = build_versions(policy, endorsements)
    selection = select_version(adm, versions, conflicts, hyp.version_id if hyp else None)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if selection.selected is None:
        return _unversioned(claim, items, selection, now, cause, hyp, hyp_notes)
    version: PolicyVersion = selection.selected
    clauses = active_clauses(version, docs)
    by_id = {c.clause_id: c for c in clauses}
    retr = retriever_for(clauses)

    ded_c, cop_c, ord_c = _first(clauses, Cat.deductible), _first(clauses, Cat.copayment), _first(clauses, Cat.computation_order)
    prec_c = _first(clauses, Cat.precedence)
    si_raw = policy.metadata.get("sum_insured", NOT_FOUND)
    hyp_params: set[str] = set()
    deductible = ded_c.interpretation.amount if ded_c else None
    copay = cop_c.interpretation.percent if cop_c else None
    if hyp and hyp.deductible is not None:
        deductible, _ = money(str(hyp.deductible)), hyp_params.add("deductible")
    if hyp and hyp.copay_percent is not None:
        copay, _ = Decimal(str(hyp.copay_percent)), hyp_params.add("copay")
    order = (ord_c.interpretation.order if ord_c and ord_c.interpretation.order else DEFAULT_ORDER)
    order_source = (f"Policy clause {ord_c.section} ({ord_c.heading})" if ord_c and ord_c.interpretation.order else
                    "ASSUMED default order — the policy does not state a computation order; review required")
    params = EngineParams(deductible=deductible, deductible_clause=ded_c.clause_id if ded_c else None,
                          deductible_used=money(str(claim.facts.deductible_used_this_year)),
                          copay_percent=copay, copay_clause=cop_c.clause_id if cop_c else None,
                          sum_insured=money(si_raw) if si_raw != NOT_FOUND else None,
                          sum_insured_used=money(str(claim.facts.sum_insured_used_this_year)),
                          order=order, order_clause=ord_c.clause_id if ord_c else None, hypothetical=hyp_params,
                          limit_overrides={k: money(str(v)) for k, v in (hyp.limit_overrides.items() if hyp else [])})

    checks = claim_checks(clauses, claim, policy, adm)
    failed = [c for c in checks if c.status == "not_satisfied"]
    unknown_checks = [c for c in checks if c.status == "unknown"]

    engine_items: list[EngineItem] = []
    decisions = {}
    for it in items:
        norm = normalize_item(it.description, it.category_hint)
        query = norm.query
        bm = retr.search(query, "bm25", CANDIDATES_PER_METHOD)
        se = retr.search(query, "semantic", CANDIDATES_PER_METHOD)
        fused = retr.search(query, "hybrid", 2 * CANDIDATES_PER_METHOD)
        cand_ids = []
        for h in fused:
            if h.clause_id in {x.clause_id for x in bm} | {x.clause_id for x in se} and h.clause_id not in cand_ids:
                cand_ids.append(h.clause_id)
        # Clauses about the item's general type of charge (e.g. "medicines" for a vitamin drip) are always considered too:
        # the positive cover often sits in such a clause, and keyword-light retrieval can rank it too low to be seen.
        if norm.general_tokens:
            for h in retr.search(" ".join(sorted(norm.general_tokens)), "bm25", CANDIDATES_PER_METHOD):
                if h.clause_id not in cand_ids:
                    cand_ids.append(h.clause_id)
        # A service dated outside the admission can only be covered by a pre/post-hospitalisation clause, so those
        # clauses are always checked for it, whatever their retrieval rank.
        if it.service_date and adm and not (adm <= it.service_date <= (dis or adm)):
            cand_ids += [c.clause_id for c in clauses if c.interpretation.category == Cat.time_window and c.clause_id not in cand_ids]
        bm_s = {h.clause_id: h.score for h in bm}
        se_s = {h.clause_id: h.score for h in se}
        ctx = ItemContext(service_date=it.service_date, admission_date=adm, discharge_date=dis)
        evidence: list[Evidence] = []
        for rank, cid in enumerate(cand_ids, start=1):
            ev = verify(by_id[cid], norm, ctx)
            ev.retrieval = {"bm25": bm_s.get(cid), "semantic": se_s.get(cid)}
            ev.retrieval_rank = rank
            evidence.append(ev)
        dec = decide(evidence, by_id, claim.facts, prec_c)
        basis = {"covered": "covered", "excluded": "excluded"}.get(dec.status, "unresolved")
        excl = [e.clause_id for e in dec.decisive if e.relation in ("exclusion", "conditional_exclusion", "precedence", "outside_window")]
        if failed:
            basis = "excluded"
            excl = [cid for c in failed for cid in c.clause_ids]
        decisions[it.item_id] = (norm, dec, evidence)
        engine_items.append(EngineItem(item_id=it.item_id, claimed=it.amount, basis=basis, quantity=it.quantity,
                                       limits=dec.limits if basis == "covered" or dec.status in ("conditional",) else dec.limits,
                                       exclusion_clauses=excl, label=f"Line {it.line_no} {it.description}"))
    low, high = run(engine_items, params, "low"), run(engine_items, params, "high")
    invariants = check_invariants(engine_items, low, high, params)

    rows: list[LedgerRow] = []
    for it, ei in zip(items, engine_items):
        norm, dec, evidence = decisions[it.item_id]
        status = STATUS_MAP[dec.status]
        review = list(dec.review)
        explanation = list(dec.explanation)
        if failed:
            status = "potentially_excluded"
            explanation.insert(0, "Claim-level waiting period not satisfied: " + "; ".join(c.detail for c in failed))
        limit_red = low.by_stage["item_limit"].get(it.item_id, ZERO) if ei.basis == "covered" else high.by_stage["item_limit"].get(it.item_id, ZERO)
        if status == "potentially_covered" and limit_red > 0:
            status = "partially_payable"
        if unknown_checks and status in ("potentially_covered", "partially_payable"):
            status = "manual_review_required"
            review.append("Claim-level eligibility check unresolved: " + "; ".join(c.check for c in unknown_checks))
        if selection.review_required and status in ("potentially_covered", "partially_payable"):
            status = "manual_review_required"
            review.append("Policy version applicability has unresolved conflicts")
        src = low if ei.basis != "unresolved" else high
        excl_amt = low.by_stage["exclusion"].get(it.item_id, ZERO)
        eligible = None if ei.basis == "unresolved" else q(it.amount - excl_amt - low.by_stage["item_limit"].get(it.item_id, ZERO))
        lim_txt = "; ".join(f"{by_id[cid].section}: {lim.text}" for cid, lim in dec.limits) or None
        if limit_red > 0:
            explanation.append(f"Item limit reduced the eligible amount by {fmt(limit_red)}.")
        if ei.basis == "unresolved":
            explanation.append(f"Not counted in the definite estimate. If resolved favourably, up to {fmt(high.payable[it.item_id])} "
                               "could be payable after cost sharing.")
        ordered = sorted(evidence, key=lambda e: (e.clause_id not in {d.clause_id for d in dec.decisive},
                                                  e.relation in ("irrelevant", "inapplicable"), e.retrieval_rank or 99))
        extra = [e for e in dec.decisive if e.clause_id not in {x.clause_id for x in ordered}]  # e.g. precedence clause
        rows.append(LedgerRow(
            item_id=it.item_id, line_no=it.line_no, original_description=it.description, normalized_description=norm.normalized,
            category=CATEGORY_LABELS.get(norm.category, norm.category), service_date=it.service_date, quantity=it.quantity,
            claimed_amount=it.amount, status=status, eligible_amount=eligible,
            item_reductions=q(excl_amt + low.by_stage["item_limit"].get(it.item_id, ZERO)),
            deductible_share=src.by_stage["deductible"].get(it.item_id, ZERO), copay_share=src.by_stage["copay"].get(it.item_id, ZERO),
            cap_share=src.by_stage["sum_insured_cap"].get(it.item_id, ZERO),
            payable_low=low.payable[it.item_id], payable_high=high.payable[it.item_id],
            patient_low=q(it.amount - high.payable[it.item_id]), patient_high=q(it.amount - low.payable[it.item_id]),
            supporting_clause_ids=[e.clause_id for e in dec.decisive], applicable_limit=lim_txt,
            explanation=" ".join(explanation), evidence_quality=dec.quality, manual_review=bool(review) or status in (
                "conditional", "insufficient_evidence", "conflicting_evidence", "manual_review_required"),
            review_reasons=review, missing_information=dec.missing, evidence=extra + ordered,
            adjustments=[a.adjustment_id for a in low.adjustments + high.adjustments if a.item_id == it.item_id],
            hypothetical=bool(hyp) and (it.item_id in (hyp.item_amounts or {}) or it.item_id in (hyp.item_quantities or {})
                                        or it.line_no >= 900)))

    total_billed = sum((i.amount for i in items), ZERO)
    unresolved_claimed = sum((i.amount for i, e in zip(items, engine_items) if e.basis == "unresolved"), ZERO)
    eligible_def = sum((r.eligible_amount for r in rows if r.eligible_amount is not None), ZERO)
    item_red = sum((r.item_reductions for r in rows), ZERO)
    pay_low, pay_high = sum(low.payable.values(), ZERO), sum(high.payable.values(), ZERO)
    expl = [
        f"Total billed: INR {fmt(total_billed)} across {len(items)} item(s) (original bill amounts, unchanged).",
        f"Definitely eligible after exclusions and item limits: INR {fmt(eligible_def)}.",
        f"Unresolved items (conditional, conflicting or insufficient evidence): INR {fmt(unresolved_claimed)} claimed — not assumed payable.",
        f"Cost sharing per {order_source}: deductible INR {fmt(low.deductible_applied)}, co-payment INR {fmt(low.copay_applied)} (definite case).",
        f"Estimated payable: INR {fmt(pay_low)} (definite) to INR {fmt(pay_high)} (if every unresolved item were resolved favourably).",
        f"Potential patient responsibility: INR {fmt(total_billed - pay_high)} to INR {fmt(total_billed - pay_low)}.",
    ] + hyp_notes + low.notes
    summary = FinancialSummary(
        total_billed=total_billed, eligible_definite=eligible_def, unresolved_claimed=unresolved_claimed, item_reductions=item_red,
        deductible_applied_low=low.deductible_applied, deductible_applied_high=high.deductible_applied,
        copay_low=low.copay_applied, copay_high=high.copay_applied, payable_low=pay_low, payable_high=pay_high,
        patient_low=q(total_billed - pay_high), patient_high=q(total_billed - pay_low), unresolved_exposure=q(pay_high - pay_low),
        computation_order=low.trace and [s.stage for s in low.trace[1:-1]], order_source=order_source, explanation=expl)
    return AnalysisResult(
        analysis_id=f"an-{uuid.uuid4().hex[:10]}", claim_id=claim.claim_id, created_at=now, cause=cause, version=selection,
        rows=rows, claim_checks=checks, summary=summary, trace_low=low.trace, trace_high=high.trace,
        adjustments=low.adjustments + high.adjustments, invariants=invariants, bill_issues=claim.bill.issues,
        hypothetical=bool(hyp), hypotheticals=hyp, synthetic=claim.synthetic, retrieval_config=retr.config())


def _unversioned(claim: Claim, items: list[BillItem], selection: VersionSelection, now: str, cause: str,
                 hyp: Optional[Hypotheticals], notes: list[str]) -> AnalysisResult:
    rows = []
    for it in items:
        norm = normalize_item(it.description, it.category_hint)
        rows.append(LedgerRow(
            item_id=it.item_id, line_no=it.line_no, original_description=it.description, normalized_description=norm.normalized,
            category=CATEGORY_LABELS.get(norm.category, norm.category), service_date=it.service_date, quantity=it.quantity,
            claimed_amount=it.amount, status="manual_review_required", eligible_amount=None, item_reductions=ZERO,
            deductible_share=ZERO, copay_share=ZERO, cap_share=ZERO, payable_low=ZERO, payable_high=ZERO,
            patient_low=ZERO, patient_high=it.amount, supporting_clause_ids=[],
            explanation="No applicable policy version could be determined, so no clause can be applied to this item.",
            evidence_quality="none", manual_review=True, review_reasons=["No applicable policy version"],
            missing_information=["Applicable policy version for the treatment date"]))
    total = sum((i.amount for i in items), ZERO)
    summary = FinancialSummary(total_billed=total, eligible_definite=ZERO, unresolved_claimed=total, item_reductions=ZERO,
                               deductible_applied_low=ZERO, deductible_applied_high=ZERO, copay_low=ZERO, copay_high=ZERO,
                               payable_low=ZERO, payable_high=ZERO, patient_low=ZERO, patient_high=total, unresolved_exposure=total,
                               computation_order=[], order_source="Not determined",
                               explanation=selection.reasons + selection.conflicts + notes +
                               ["No estimate can be produced until the applicable policy version is resolved."])
    return AnalysisResult(analysis_id=f"an-{uuid.uuid4().hex[:10]}", claim_id=claim.claim_id, created_at=now, cause=cause,
                          version=selection, rows=rows, claim_checks=[], summary=summary, trace_low=[], trace_high=[],
                          adjustments=[], invariants=[], bill_issues=claim.bill.issues, hypothetical=bool(hyp),
                          hypotheticals=hyp, synthetic=claim.synthetic)
