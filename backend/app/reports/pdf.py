"""Claim report export (PDF via PyMuPDF Story, plus structured JSON). Reports contain only pipeline output."""
from __future__ import annotations

import html
import io

import pymupdf

from app.models import AnalysisResult, Claim, DocumentRecord
from app.money import fmt

STATUS = {"potentially_covered": "Potentially covered", "partially_payable": "Partially payable",
          "potentially_excluded": "Potentially excluded", "conditional": "Conditional",
          "insufficient_evidence": "Insufficient evidence", "conflicting_evidence": "Conflicting evidence",
          "manual_review_required": "Manual review required"}

CSS = """
body { font-family: sans-serif; font-size: 9pt; color: #1b2430; }
h1 { font-size: 18pt; color: #0f2a3a; margin-bottom: 2pt; }
h2 { font-size: 12pt; color: #0f2a3a; margin-top: 14pt; border-bottom: 1px solid #c9d2d9; }
.tag { color: #8a4b12; font-weight: bold; }
.muted { color: #5b6672; }
table { border-collapse: collapse; width: 100%; }
th { background-color: #e8eef2; text-align: left; font-size: 8pt; padding: 3pt; }
td { border-bottom: 1px solid #e1e6ea; padding: 3pt; font-size: 8pt; vertical-align: top; }
.num { text-align: right; }
"""


def _e(s) -> str:
    s = str(s).replace("–", "-").replace("—", "-").replace("→", "->").replace("₹", "INR ").replace("≤", "<=")
    return html.escape(s)


def build_html(claim: Claim, a: AnalysisResult, docs: dict[str, DocumentRecord], fair: dict | None = None, acts: dict | None = None) -> str:
    s = a.summary
    v = a.version
    clauses = {c.clause_id: c for d in docs.values() for c in d.clauses}
    parts = [f"<h1>Nivaaran claim analysis report</h1><p class='muted'>Insurance clarity. Backed by evidence.</p>"]
    if a.synthetic or claim.synthetic:
        parts.append("<p class='tag'>SYNTHETIC DEMONSTRATION DATA - not a real policy, bill or claim.</p>")
    if a.hypothetical:
        parts.append("<p class='tag'>Contains HYPOTHETICAL What-If inputs - not based solely on the documents.</p>")
    parts.append(f"<p><b>Claim:</b> {_e(claim.title)} &nbsp; <b>Diagnosis:</b> {_e(claim.diagnosis)} &nbsp; "
                 f"<b>Admission:</b> {_e(claim.admission_date)} &nbsp; <b>Analysis:</b> {_e(a.analysis_id)} ({_e(a.created_at)})</p>")
    parts.append("<h2>Claim summary</h2><table>")
    for k, val in [("Total billed (original amounts)", s.total_billed), ("Definitely eligible after exclusions and limits", s.eligible_definite),
                   ("Unresolved items (claimed)", s.unresolved_claimed), ("Deductible applied (definite case)", s.deductible_applied_low),
                   ("Co-payment (definite case)", s.copay_low)]:
        parts.append(f"<tr><td>{_e(k)}</td><td class='num'>INR {fmt(val)}</td></tr>")
    parts.append(f"<tr><td><b>Estimated payable (range)</b></td><td class='num'><b>INR {fmt(s.payable_low)} - {fmt(s.payable_high)}</b></td></tr>")
    parts.append(f"<tr><td><b>Potential patient responsibility (range)</b></td><td class='num'><b>INR {fmt(s.patient_low)} - {fmt(s.patient_high)}</b></td></tr></table>")
    parts.append("<h2>Selected policy version</h2>")
    parts.append(f"<p><b>{_e(v.selected.label if v.selected else 'None determined')}</b></p><ul>" +
                 "".join(f"<li>{_e(r)}</li>" for r in v.reasons + v.conflicts) + "</ul>")
    parts.append("<h2>Itemised adjudication ledger</h2><table><tr><th>#</th><th>Bill item</th><th>Category</th><th>Status</th>"
                 "<th class='num'>Claimed</th><th class='num'>Eligible</th><th class='num'>Est. payable</th><th>Clauses</th></tr>")
    for r in a.rows:
        elig = fmt(r.eligible_amount) if r.eligible_amount is not None else "unresolved"
        pay = fmt(r.payable_low) if r.payable_low == r.payable_high or r.eligible_amount is not None else f"0.00 - {fmt(r.payable_high)}"
        parts.append(f"<tr><td>{r.line_no}</td><td>{_e(r.original_description)}</td><td>{_e(r.category)}</td>"
                     f"<td>{_e(STATUS[r.status])}{' *' if r.manual_review else ''}</td><td class='num'>{fmt(r.claimed_amount)}</td>"
                     f"<td class='num'>{elig}</td><td class='num'>{pay}</td>"
                     f"<td>{_e(', '.join(c.split(':')[1] for c in r.supporting_clause_ids) or '-')}</td></tr>")
    parts.append("</table><p class='muted'>* manual review required. Estimated payable for resolved items is the definite case; "
                 "unresolved items show the range 0 to the favourable-resolution amount.</p>")
    parts.append("<h2>Item explanations</h2>")
    for r in a.rows:
        parts.append(f"<p><b>Line {r.line_no} - {_e(r.original_description)}:</b> {_e(r.explanation)}</p>")
    parts.append("<h2>Evidence citations</h2><table><tr><th>Clause</th><th>Document / page</th><th>Exact excerpt</th></tr>")
    cited = []
    for r in a.rows:
        for cid in r.supporting_clause_ids:
            if cid not in cited and cid in clauses:
                cited.append(cid)
    for st in a.trace_low:
        for cid in st.clause_ids:
            if cid not in cited and cid in clauses:
                cited.append(cid)
    for cid in cited:
        c = clauses[cid]
        d = docs[c.document_id]
        parts.append(f"<tr><td>{_e(c.section)} {_e(c.heading)}</td><td>{_e(d.filename)}, p. {c.page}</td><td>{_e(c.text)}</td></tr>")
    parts.append("</table><h2>Calculation trace (definite case)</h2><table><tr><th>Step</th><th>Stage</th><th>Description</th>"
                 "<th class='num'>Before</th><th class='num'>After</th></tr>")
    for t in a.trace_low:
        parts.append(f"<tr><td>{t.step_no}</td><td>{_e(t.stage)}</td><td>{_e(t.description)}</td><td class='num'>{fmt(t.amount_before)}</td>"
                     f"<td class='num'>{fmt(t.amount_after)}</td></tr>")
    parts.append(f"</table><p class='muted'>Order source: {_e(s.order_source)}</p>")
    parts.append("<h2>Unresolved questions and review requirements</h2><ul>")
    for r in a.rows:
        if r.manual_review:
            parts.append(f"<li>Line {r.line_no} {_e(r.original_description)}: {_e('; '.join(r.review_reasons + r.missing_information))}</li>")
    for c in a.claim_checks:
        if c.status in ("unknown", "not_satisfied"):
            parts.append(f"<li>{_e(c.check)}: {_e(c.detail)}</li>")
    for bi in a.bill_issues:
        parts.append(f"<li>Bill check ({bi.severity}): {_e(bi.message)}</li>")
    parts.append("</ul>")
    if fair:
        parts.append(f"<h2>Fraud &amp; fairness review (separate from coverage analysis)</h2><p><b>{_e(fair['status_label'])}.</b> {_e(fair['method'])}</p>")
        for f in fair["findings"]:
            parts.append(f"<p><b>[{_e(f['severity'])} severity, evidence {_e(f['evidence_completeness'])}] {_e(f['category_label'])}: {_e(f['title'])}</b><br/>{_e(f['explanation'])}</p>")
        parts.append("<p class='muted'>Automated discrepancy checks, not a legal determination of fraud or misconduct.</p>")
    if acts:
        parts.append("<h2>Suggested next steps</h2><ul>")
        for q in acts["questions"]:
            parts.append(f"<li>{_e(q['question'])}</li>")
        for s in acts["general_steps"]:
            parts.append(f"<li>{_e(s)}</li>")
        parts.append("</ul>")
    parts.append("<h2>Limitations and disclaimer</h2>")
    parts.append(f"<p>{_e(a.disclaimer)} Figures are estimates computed deterministically from the documents provided and the "
                 "stated claim facts. Clause interpretation is pattern-based and should be confirmed against the full policy "
                 "wording. Retrieval relevance scores indicate textual similarity only and are not probabilities of coverage.</p>")
    inv_fail = [i for i in a.invariants if not i["passed"]]
    parts.append(f"<p class='muted'>Engine invariant checks: {len(a.invariants) - len(inv_fail)}/{len(a.invariants)} passed.</p>")
    return "".join(parts)


def render_pdf(claim: Claim, a: AnalysisResult, docs: dict[str, DocumentRecord], fair: dict | None = None, acts: dict | None = None) -> bytes:
    story = pymupdf.Story(html=build_html(claim, a, docs, fair, acts), user_css=CSS)
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    media = pymupdf.paper_rect("a4")
    where = media + (40, 44, -40, -44)
    more = True
    while more:
        dev = writer.begin_page(media)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    return buf.getvalue()
