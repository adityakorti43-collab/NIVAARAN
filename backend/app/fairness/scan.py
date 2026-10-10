"""Fraud & Fairness Intelligence — transparent, rule-based discrepancy detection over extracted evidence.

Nothing here is a fraud classifier and nothing here scores "probability of fraud". Each finding comes from a
named, deterministic check over clauses, bill lines and engine output, and carries the exact excerpts that
triggered it. Findings are graded on two separate axes: severity (how much it could matter) and evidence
completeness (how fully the supplied documents establish it).

Categories (lowest to highest concern):
  restrictive_documented   a restrictive term that is clearly documented — NOT a discrepancy
  ambiguous_clause         wording that leaves room for more than one reading
  document_contradiction   two supplied documents (or clauses) disagree
  representation_gap       a benefit summary / brochure states something the issued wording does not
  calculation_inconsistency arithmetic or deduction that does not reconcile
  investigation_warranted  several issues together that merit further enquiry
Fraud is never "established" by this tool; that requires a competent authority.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Optional

from app.models import AnalysisResult, Claim, Clause, ClauseCategory as Cat, DocType, DocumentRecord
from app.money import fmt
from app.policy.versions import active_clauses, build_versions
from app.retrieval.text import content_tokens

CATEGORY_LABEL = {
    "restrictive_documented": "Restrictive but documented term",
    "ambiguous_clause": "Ambiguous clause",
    "document_contradiction": "Contradiction between supplied documents",
    "representation_gap": "Benefit summary differs from issued policy",
    "calculation_inconsistency": "Calculation or deduction inconsistency",
    "investigation_warranted": "Further investigation warranted",
}
VAGUE = re.compile(r"\b(similar|reasonable and customary|medically necessary|as applicable|at the discretion|other such|and the like)\b", re.I)


def _ex(c: Clause, docs: dict[str, DocumentRecord]) -> dict:
    d = docs.get(c.document_id)
    return {"clause_id": c.clause_id, "section": c.section, "heading": c.heading, "page": c.page, "text": c.text,
            "document_id": c.document_id, "document": d.metadata.get("title", d.filename) if d else c.document_id,
            "doc_type": c.doc_type.value}


def _terms(c: Clause) -> set[str]:
    return {t for term in c.interpretation.scope_terms for t in content_tokens(term)}


def _match(summary: Clause, pool: list[Clause], cats: set[Cat]) -> Optional[Clause]:
    st = _terms(summary)
    best, score = None, 0.0
    for c in pool:
        if c.interpretation.category not in cats:
            continue
        ct = _terms(c)
        if not st or not ct:
            continue
        s = len(st & ct) / len(st | ct)
        if s > score:
            best, score = c, s
    return best if score >= 0.34 else None


ALTERNATIVES = {
    "representation_gap": ["The summary may describe a different plan variant, policy year or add-on.",
                           "The summary may be out of date relative to a later endorsement."],
    "document_contradiction": ["One clause may be intended as an exception to the other; the wording does not say which."],
    "calculation_inconsistency": ["The bill may include a discount, tax or package charge not shown as a line item.",
                                  "Two similar lines may be separate services on different days."],
    "ambiguous_clause": ["The insurer may apply a published list or internal guideline that defines the term."],
    "investigation_warranted": ["Each issue may have an independent, legitimate explanation."],
    "restrictive_documented": [],
}


def _finding(fid, category, title, explanation, why, excerpts, severity, completeness, questions, steps, conflicting=None,
             status="potential_discrepancy", impact=None):
    return {"id": fid, "category": category, "category_label": CATEGORY_LABEL[category], "title": title,
            "alternative_explanations": ALTERNATIVES.get(category, []), "human_review_required": True,
            "financial_impact": impact,
            "explanation": explanation, "why_it_matters": why, "excerpts": excerpts, "conflicting_excerpts": conflicting or [],
            "severity": severity, "evidence_completeness": completeness, "unresolved_questions": questions,
            "next_steps": steps, "status": status,
            "documents": sorted({e["document"] for e in excerpts + (conflicting or [])})}


def _copay_impact(analysis: AnalysisResult, policy_pct, summary_pct) -> Optional[str]:
    step = next((s for s in analysis.trace_low if s.stage == "copay"), None)
    if not step or policy_pct is None or summary_pct is None:
        return None
    return str((step.amount_before * (Decimal(policy_pct) - Decimal(summary_pct)) / Decimal(100)).quantize(Decimal("0.01")))


def _limit_impact(analysis: AnalysisResult, clause_id: str, s_amt, p_amt, basis: str) -> Optional[str]:
    if basis != "per_day":
        return None
    total = Decimal("0")
    for r in analysis.rows:
        if clause_id in r.supporting_clause_ids:
            total += max(Decimal("0"), min(r.claimed_amount, s_amt * r.quantity) - min(r.claimed_amount, p_amt * r.quantity))
    return str(total.quantize(Decimal("0.01"))) if total else None


def scan(claim: Claim, analysis: AnalysisResult, docs: dict[str, DocumentRecord]) -> dict:
    findings: list[dict] = []
    checks: list[dict] = []
    policy = docs[claim.policy_document_id]
    version = analysis.version.selected
    clauses = active_clauses(version, docs) if version else policy.clauses
    summaries = [docs[s] for s in claim.benefit_summary_ids if s in docs]

    # 1. Benefit summary vs issued wording -------------------------------------------------------
    for s in summaries:
        for sc in s.clauses:
            it = sc.interpretation
            if it.category == Cat.copayment:
                pc = next((c for c in clauses if c.interpretation.category == Cat.copayment), None)
                if pc and pc.interpretation.percent != it.percent:
                    findings.append(_finding(
                        f"rep-{sc.section}", "representation_gap", f"Co-payment stated as {it.percent}% but the policy applies {pc.interpretation.percent}%",
                        f"The benefit summary says the co-payment is {it.percent}%. The policy wording applicable on the treatment date "
                        f"({version.label if version else 'unknown version'}) sets it at {pc.interpretation.percent}% in clause {pc.section}.",
                        "Co-payment applies to the whole admissible claim, so the difference changes what you may pay on every covered item.",
                        [_ex(sc, docs)], "high", "complete",
                        ["Which document governs your contract: the summary or the issued wording?", "Was the summary provided before purchase, and for this policy year?"],
                        ["Ask the insurer in writing to confirm the applicable co-payment and identify the governing clause.",
                         "Keep a copy of the benefit summary and when you received it."], [_ex(pc, docs)],
                        impact=_copay_impact(analysis, pc.interpretation.percent, it.percent)))
                elif pc:
                    checks.append({"check": f"Co-payment in {s.filename}", "result": "consistent", "detail": f"{it.percent}% in both documents."})
            elif it.category == Cat.deductible:
                pc = next((c for c in clauses if c.interpretation.category == Cat.deductible), None)
                if pc and pc.interpretation.amount != it.amount:
                    findings.append(_finding(f"rep-{sc.section}", "representation_gap", "Deductible differs between documents",
                                             f"The summary states INR {fmt(it.amount)}; clause {pc.section} states INR {fmt(pc.interpretation.amount)}.",
                                             "The deductible is subtracted before co-payment, so it directly changes the estimate.",
                                             [_ex(sc, docs)], "high", "complete", ["Which amount applies to this policy year?"],
                                             ["Request written confirmation of the deductible."], [_ex(pc, docs)]))
                elif pc:
                    checks.append({"check": f"Deductible in {s.filename}", "result": "consistent", "detail": f"INR {fmt(it.amount)} in both documents."})
            elif it.category in (Cat.limit, Cat.coverage):
                pc = _match(sc, clauses, {Cat.limit, Cat.coverage, Cat.exclusion, Cat.conditional_exclusion})
                if not pc:
                    checks.append({"check": f"{sc.heading} in {s.filename}", "result": "no_counterpart",
                                   "detail": "No comparable clause found in the applicable wording; not treated as a discrepancy."})
                    continue
                pi = pc.interpretation
                s_amt = it.limit.amount if it.limit else None
                p_amt = pi.limit.amount if pi.limit else None
                if pi.category in (Cat.exclusion, Cat.conditional_exclusion):
                    findings.append(_finding(f"rep-{sc.section}", "representation_gap", f"{sc.heading}: summary says payable, policy excludes",
                                             f"The summary says '{sc.text}' but clause {pc.section} of the applicable wording excludes or restricts it.",
                                             "A benefit you were told is covered may not be paid under the issued wording.",
                                             [_ex(sc, docs)], "high", "complete", ["Which document governs?"],
                                             ["Ask the insurer to reconcile the summary with the wording."], [_ex(pc, docs)]))
                elif s_amt is not None and p_amt is not None and (s_amt != p_amt or it.limit.basis != pi.limit.basis):
                    more = s_amt > p_amt
                    findings.append(_finding(f"rep-{sc.section}", "representation_gap",
                                             f"{sc.heading}: INR {fmt(s_amt)} in the summary vs INR {fmt(p_amt)} in the policy",
                                             f"The summary states {it.limit.text}; the applicable clause {pc.section} states {pi.limit.text}."
                                             + (" The summary is more generous than the issued wording." if more else ""),
                                             "Limits cap what can be paid for each item; a higher represented limit would reduce your out-of-pocket amount.",
                                             [_ex(sc, docs)], "high" if more else "medium", "complete",
                                             ["Was this summary issued for this policy and period?", "Which limit does the insurer apply?"],
                                             ["Ask the insurer to confirm the limit in writing, citing both documents.",
                                              "Compare with any other benefit material you received at purchase."], [_ex(pc, docs)],
                                             impact=_limit_impact(analysis, pc.clause_id, s_amt, p_amt, pi.limit.basis)))
                elif s_amt is None and p_amt is not None:
                    findings.append(_finding(f"rep-{sc.section}", "representation_gap", f"{sc.heading}: the summary omits a cap",
                                             f"The summary says '{sc.text}' without a limit; clause {pc.section} caps it at {pi.limit.text}.",
                                             "An omitted cap can make a benefit look larger than the wording allows.",
                                             [_ex(sc, docs)], "medium", "complete", ["Does the cap apply to your claim?"],
                                             ["Ask the insurer to confirm whether the cap applies."], [_ex(pc, docs)]))
                else:
                    checks.append({"check": f"{sc.heading} in {s.filename}", "result": "consistent",
                                   "detail": f"Matches clause {pc.section}" + (f" ({pi.limit.text})." if pi.limit else ".")})

    # 2. Contradictions between supplied clauses (from the ledger's conflict verdicts) -------------
    by_id = {c.clause_id: c for d in docs.values() for c in d.clauses}
    for r in analysis.rows:
        if r.status == "conflicting_evidence":
            ex = [_ex(by_id[c], docs) for c in r.supporting_clause_ids if c in by_id]
            if len(ex) >= 2:
                findings.append(_finding(f"conflict-{r.item_id}", "document_contradiction", f"Clauses disagree about '{r.original_description}'",
                                         r.explanation, "The documents do not establish whether this charge is payable; it should not be decided either way without clarification.",
                                         ex[:1], "medium", "complete", ["Which clause does the insurer treat as governing, and why?"],
                                         ["Ask the insurer which clause applies to this charge and why."], ex[1:]))

    # 3. Policy-version / amendment date problems ---------------------------------------------------
    for i, msg in enumerate(analysis.version.conflicts):
        findings.append(_finding(f"version-{i}", "document_contradiction", "Amendment applicability is unclear", msg,
                                 "If the wrong wording is applied, every limit and cost-sharing term in the estimate can change.",
                                 [], "medium", "partial", ["What is the effective date of this amendment?"],
                                 ["Request the dated endorsement schedule from the insurer."], status="clarification_recommended"))

    # 4. Bill arithmetic -------------------------------------------------------------------------
    for i, b in enumerate(claim.bill.issues):
        if b.severity == "error":
            findings.append(_finding(f"bill-{i}", "calculation_inconsistency", "Bill arithmetic does not reconcile", b.message,
                                     "If line totals don't add up, the amount claimed may be wrong before any policy rule is applied.",
                                     [], "medium", "complete", ["Which figure on the bill is correct?"],
                                     ["Ask the hospital for a corrected itemised bill."]))
        checks.append({"check": "Bill arithmetic", "result": "issue" if b.severity == "error" else "note", "detail": b.message})
    if not claim.bill.issues:
        checks.append({"check": "Bill arithmetic", "result": "consistent", "detail": "Every line and the stated total reconcile."})

    # 4b. Duplicate-looking bill lines ------------------------------------------------------------
    seen_lines: dict[tuple, str] = {}
    dup_found = False
    for it in claim.bill.items:
        key = (" ".join(sorted(content_tokens(it.description))), it.amount, it.service_date)
        if key in seen_lines:
            dup_found = True
            findings.append(_finding(f"dup-{it.item_id}", "calculation_inconsistency", f"Possible duplicate bill line: '{it.description}'",
                                     f"Line {it.line_no} matches {seen_lines[key]} in description, amount (INR {fmt(it.amount)}) and date.",
                                     "If it is a duplicate, the claimed total is overstated before any policy rule applies.",
                                     [], "medium", "partial", ["Are these two separate services?"],
                                     ["Ask the hospital to confirm or correct the duplicated line."], impact=str(it.amount)))
        else:
            seen_lines[key] = f"line {it.line_no}"
    checks.append({"check": "Duplicate bill lines", "result": "issue" if dup_found else "consistent",
                   "detail": "Possible duplicates found." if dup_found else "No two lines share description, amount and date."})

    # 5. Engine consistency ----------------------------------------------------------------------
    failed = [x for x in analysis.invariants if not x["passed"]]
    checks.append({"check": "Estimate reconciliation", "result": "issue" if failed else "consistent",
                   "detail": f"{len(analysis.invariants) - len(failed)}/{len(analysis.invariants)} engine invariants passed."})

    # 6. Clause numbering gaps (possible missing pages) ------------------------------------------
    for d in [policy] + [docs[e] for e in claim.endorsement_ids if e in docs]:
        groups: dict[str, list[int]] = {}
        for c in d.clauses:
            m = re.match(r"^([A-Z]?\d+)\.(\d+)$", c.section)
            if m:
                groups.setdefault(m.group(1), []).append(int(m.group(2)))
        gaps = [f"{g}.{n}" for g, nums in groups.items() for n in range(1, max(nums) + 1) if n not in nums]
        if gaps:
            findings.append(_finding(f"gap-{d.document_id}", "document_contradiction", f"Clause numbers missing in {d.filename}",
                                     f"Clauses {', '.join(gaps[:8])} are referenced by the numbering sequence but were not found. Pages may be missing.",
                                     "A missing clause could contain an exclusion or a benefit that changes the result.", [], "medium", "partial",
                                     ["Is the complete policy wording available?"], ["Request the complete policy wording."], status="clarification_recommended"))
        else:
            checks.append({"check": f"Clause numbering in {d.filename}", "result": "consistent", "detail": "No gaps in clause numbering."})

    # 7. Ambiguous wording ------------------------------------------------------------------------
    for c in clauses:
        m = VAGUE.search(c.text)
        if m and c.interpretation.category in (Cat.exclusion, Cat.conditional_exclusion, Cat.definition, Cat.coverage):
            findings.append(_finding(f"vague-{c.section}", "ambiguous_clause", f"Open-ended wording in clause {c.section}",
                                     f"Clause {c.section} uses '{m.group(0)}', which does not define exactly what is included.",
                                     "Open-ended terms can be read narrowly or broadly; ask how the insurer applies them.",
                                     [_ex(c, docs)], "low", "complete", [f"How does the insurer interpret '{m.group(0)}'?"],
                                     ["Ask for the insurer's interpretation or a list of what the term includes."], status="clarification_recommended"))

    # 8. Restrictive terms that are clearly documented (explicitly NOT discrepancies) -------------
    restrictive = []
    for r in analysis.rows:
        if r.status == "potentially_excluded":
            ex = [_ex(by_id[c], docs) for c in r.supporting_clause_ids if c in by_id]
            restrictive.append({"item": r.original_description, "amount": str(r.claimed_amount), "excerpts": ex,
                                "note": "Excluded by a clearly worded clause. This is a documented term, not evidence of misconduct."})

    serious = [f for f in findings if f["category"] in ("representation_gap", "calculation_inconsistency")]
    if len(serious) >= 2:
        findings.insert(0, _finding("multi", "investigation_warranted", f"{len(serious)} issues together merit a written clarification",
                                    "Several independent discrepancies were found between the documents you supplied.",
                                    "Individually each may have an explanation; together they justify asking the insurer to reconcile them in writing.",
                                    [], "high", "partial", ["Can the insurer reconcile each item in one written response?"],
                                    ["Use the Action Center to draft a neutral clarification request covering every item.",
                                     "Preserve all documents and correspondence.",
                                     "If the response is unsatisfactory, consider the insurer's grievance process or professional advice."]))
    status = ("insufficient_evidence" if not summaries and not findings else
              "multiple_issues" if len(serious) >= 2 else
              "potential_discrepancy" if serious else
              "clarification_recommended" if findings else "no_significant_discrepancy")
    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (f["id"] != "multi", order[f["severity"]]))
    return {
        "status": status,
        "status_label": {"insufficient_evidence": "Insufficient evidence for a comparison", "multiple_issues": "Multiple issues require review",
                         "potential_discrepancy": "Potential discrepancy identified", "clarification_recommended": "Clarification recommended",
                         "no_significant_discrepancy": "No significant discrepancy identified in the reviewed documents"}[status],
        "findings": findings, "checks": checks, "restrictive_terms": restrictive,
        "documents_reviewed": [{"document_id": d.document_id, "filename": d.filename, "doc_type": d.doc_type.value,
                                "title": d.metadata.get("title", d.filename)} for d in [policy] + [docs[e] for e in claim.endorsement_ids if e in docs] + summaries],
        "method": "Each check is a fixed rule that compares your documents, the bill and the calculation. There is no fraud score and "
                  "no guesswork. How serious a finding is and how well the documents support it are rated separately.",
        "limitations": ["Only the documents you supplied are compared; advertisements or verbal representations are not assessed unless uploaded.",
                        "A clean result means no discrepancy was found in these documents — not that none exists.",
                        "Nothing here is a legal determination of fraud or misconduct."],
    }
