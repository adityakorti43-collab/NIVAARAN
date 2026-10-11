"""Consumer Action Center: practical next steps and a neutral clarification letter, built only from findings.

The letter asks questions; it never alleges fraud, never cites legal deadlines or regulations, and is
returned for the consumer to review and edit. Nothing is sent anywhere.
"""
from __future__ import annotations

from datetime import date

from app.models import AnalysisResult, Claim, DocumentRecord
from app.money import fmt


def build_actions(claim: Claim, a: AnalysisResult, fair: dict, docs: dict[str, DocumentRecord]) -> dict:
    policy = docs[claim.policy_document_id]
    pno = policy.metadata.get("policy_number", "[policy number]")
    questions: list[dict] = []
    for r in a.rows:
        secs = ", ".join(c.split(":")[1] for c in r.supporting_clause_ids) or "none identified"
        if r.status == "conflicting_evidence":
            questions.append({"topic": r.original_description, "item_id": r.item_id, "clauses": r.supporting_clause_ids,
                              "question": f"For '{r.original_description}' (INR {fmt(r.claimed_amount)}), clauses {secs} appear to disagree. Which clause applies, and why?"})
        elif r.status in ("conditional", "insufficient_evidence"):
            need = "; ".join(r.missing_information) or "the clause that applies"
            questions.append({"topic": r.original_description, "item_id": r.item_id, "clauses": r.supporting_clause_ids,
                              "question": f"For '{r.original_description}' (INR {fmt(r.claimed_amount)}), please confirm how it will be assessed. Information needed: {need}."})
        elif r.status == "partially_payable":
            questions.append({"topic": r.original_description, "item_id": r.item_id, "clauses": r.supporting_clause_ids,
                              "question": f"For '{r.original_description}', please confirm the limit applied ({r.applicable_limit or secs}) and the resulting eligible amount."})
    for f in fair["findings"]:
        if f["category"] in ("representation_gap", "document_contradiction", "calculation_inconsistency"):
            questions.append({"topic": f["title"], "finding_id": f["id"], "clauses": [e["clause_id"] for e in f["excerpts"] + f["conflicting_excerpts"]],
                              "question": f"{f['title']}. " + (f["unresolved_questions"][0] if f["unresolved_questions"] else "Please explain.")})
    missing_docs = sorted({m for r in a.rows for m in r.missing_information})
    unresolved_inputs = [{"item": r.original_description, "range": [str(r.payable_low), str(r.payable_high)], "why": r.explanation}
                         for r in a.rows if r.eligible_amount is None]
    excerpts = []
    seen = set()
    for q in questions:
        for cid in q.get("clauses", []):
            if cid in seen:
                continue
            seen.add(cid)
            c = next((c for d in docs.values() for c in d.clauses if c.clause_id == cid), None)
            if c:
                excerpts.append({"clause_id": cid, "section": c.section, "heading": c.heading, "page": c.page, "text": c.text})
    return {
        "summary": {"version": a.version.selected.label if a.version.selected else None, "payable": [str(a.summary.payable_low), str(a.summary.payable_high)],
                    "patient": [str(a.summary.patient_low), str(a.summary.patient_high)], "review_items": sum(r.manual_review for r in a.rows),
                    "fairness_status": fair["status_label"]},
        "questions": questions, "missing_documents": missing_docs, "unresolved_inputs": unresolved_inputs, "excerpts": excerpts,
        "general_steps": [
            "Ask questions in writing and keep copies of every reply.",
            "Keep the policy wording, endorsements, benefit summaries and bills you received, with the dates you received them.",
            "If a reply does not resolve the issue, ask the insurer about its grievance process, or seek professional advice.",
        ],
        "letter": draft_letter(claim, a, fair, questions, pno),
    }


def draft_letter(claim: Claim, a: AnalysisResult, fair: dict, questions: list[dict], pno: str) -> str:
    lines = [
        "Subject: Request for clarification — policy " + pno,
        "",
        "Dear Claims Team,",
        "",
        f"I am writing about my hospitalisation that began on {claim.admission_date.strftime('%d %B %Y')}"
        + (f" ({claim.diagnosis})" if claim.diagnosis and not claim.diagnosis.startswith("Not found") else "")
        + f", with a bill totalling INR {fmt(a.summary.total_billed)}. Before I submit or follow up on my claim, I would be grateful "
          "if you could clarify the points below, referring to the specific policy clauses that apply.",
        "",
    ]
    for i, q in enumerate(questions, start=1):
        lines.append(f"{i}. {q['question']}")
    if not questions:
        lines.append("1. Please confirm how each item on the enclosed itemised bill will be assessed, and the clause that applies to it.")
    lines += [
        "",
        "Please also confirm which policy wording and endorsements you consider applicable to the treatment date, with their effective dates.",
        "",
        "I have enclosed copies of the documents I am relying on. I would appreciate a written reply.",
        "",
        "Yours faithfully,",
        "[Your name]",
        f"[Contact details]  ·  Date: {date.today().strftime('%d %B %Y')}",
    ]
    return "\n".join(lines)
