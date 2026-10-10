"""Before/after comparison of two analyses, with a stated reason for every material change."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.models import AnalysisResult
from app.money import ZERO, fmt

STATUS_TEXT = {"potentially_covered": "potentially covered", "partially_payable": "partially payable",
               "potentially_excluded": "potentially excluded", "conditional": "conditional",
               "insufficient_evidence": "insufficient evidence", "conflicting_evidence": "conflicting evidence",
               "manual_review_required": "manual review required"}


def _sec(cid: str) -> str:
    return cid.split(":", 1)[1] if ":" in cid else cid


def compare(prev: AnalysisResult, new: AnalysisResult, cause: str) -> dict:
    reasons: list[str] = []
    pv, nv = prev.version.selected, new.version.selected
    if (pv and pv.version_id) != (nv and nv.version_id):
        reasons.append(f"Applicable policy version changed from '{pv.label if pv else 'none'}' to '{nv.label if nv else 'none'}'. "
                       + (" ".join(new.version.reasons[:2])))
    pclauses = {cid for r in prev.rows for cid in r.supporting_clause_ids}
    nclauses = {cid for r in new.rows for cid in r.supporting_clause_ids}
    if nv:
        for old, rep in nv.superseded_sections.items():
            if (not pv or old not in pv.superseded_sections):
                reasons.append(f"Clause {_sec(old)} is replaced by {_sec(rep)} in the applicable version.")
    prow = {r.item_id: r for r in prev.rows}
    nrow = {r.item_id: r for r in new.rows}
    items = []
    for iid in list(dict.fromkeys(list(prow) + list(nrow))):
        a, b = prow.get(iid), nrow.get(iid)
        if a and not b:
            items.append({"item_id": iid, "description": a.original_description, "change": "removed",
                          "payable_before": str(a.payable_low), "payable_after": "0.00",
                          "delta": str(-a.payable_low), "reason": "Item removed from the bill or scenario."})
            continue
        if b and not a:
            items.append({"item_id": iid, "description": b.original_description, "change": "added",
                          "payable_before": "0.00", "payable_after": str(b.payable_low), "delta": str(b.payable_low),
                          "reason": "Item added to the bill or scenario."})
            continue
        why = []
        if a.claimed_amount != b.claimed_amount:
            why.append(f"claimed amount {fmt(a.claimed_amount)} -> {fmt(b.claimed_amount)}")
        if a.status != b.status:
            why.append(f"status {STATUS_TEXT[a.status]} -> {STATUS_TEXT[b.status]}")
        sa, sb = set(a.supporting_clause_ids), set(b.supporting_clause_ids)
        if sa != sb:
            why.append("evidence " + ", ".join(_sec(c) for c in sorted(sa)) + " -> " + ", ".join(_sec(c) for c in sorted(sb)))
        if (a.eligible_amount or ZERO) != (b.eligible_amount or ZERO) and a.claimed_amount == b.claimed_amount and a.status == b.status:
            why.append(f"eligible amount {fmt(a.eligible_amount or ZERO)} -> {fmt(b.eligible_amount or ZERO)} "
                       f"({b.applicable_limit or 'limit changed'})")
        if a.payable_low != b.payable_low or a.payable_high != b.payable_high or why:
            if not why:
                why.append("share of claim-level deductible/co-payment changed because other items or cost-sharing terms changed")
            items.append({"item_id": iid, "description": b.original_description, "change": "changed",
                          "status_before": a.status, "status_after": b.status,
                          "clauses_before": [_sec(c) for c in a.supporting_clause_ids],
                          "clauses_after": [_sec(c) for c in b.supporting_clause_ids],
                          "payable_before": str(a.payable_low), "payable_after": str(b.payable_low),
                          "payable_high_before": str(a.payable_high), "payable_high_after": str(b.payable_high),
                          "delta": str(b.payable_low - a.payable_low), "reason": "; ".join(why) + "."})
    steps = []
    pt = {s.stage: s for s in prev.trace_low}
    for s in new.trace_low:
        o = pt.get(s.stage)
        if not o or o.description != s.description or o.amount_after != s.amount_after:
            steps.append({"stage": s.stage, "before": o.description if o else None, "after": s.description,
                          "amount_before": str(o.amount_after) if o else None, "amount_after": str(s.amount_after)})
    ps, ns = prev.summary, new.summary
    dp = ns.payable_low - ps.payable_low
    doop = ns.patient_high - ps.patient_high
    if not reasons and not items:
        reasons.append("No change in the estimate.")
    if new.hypothetical:
        reasons.append("The updated result includes HYPOTHETICAL What-If inputs; it is not based solely on the documents.")
    return {
        "comparison_id": f"cmp-{uuid.uuid4().hex[:10]}", "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cause": cause, "previous_analysis_id": prev.analysis_id, "updated_analysis_id": new.analysis_id,
        "previous_version": pv.label if pv else None, "updated_version": nv.label if nv else None,
        "reasons": reasons, "changed_items": items, "changed_steps": steps,
        "changed_clauses": {"added": sorted(_sec(c) for c in nclauses - pclauses), "removed": sorted(_sec(c) for c in pclauses - nclauses)},
        "payable_before": [str(ps.payable_low), str(ps.payable_high)], "payable_after": [str(ns.payable_low), str(ns.payable_high)],
        "payable_delta": str(dp), "payable_high_delta": str(ns.payable_high - ps.payable_high),
        "patient_before": [str(ps.patient_low), str(ps.patient_high)], "patient_after": [str(ns.patient_low), str(ns.patient_high)],
        "patient_delta": str(doop), "hypothetical": new.hypothetical,
    }
