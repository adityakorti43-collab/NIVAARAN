"""Policy-only tools: what the app can tell you from your policy before you have a claim.

  estimate()   run the real claim calculation on a hypothetical stay (nothing is saved)
  ask()        answer a question from the policy's own clauses, in English or Hindi, with citations
  checklist()  practical next steps: claim documents, waiting-period dates, what you pay yourself
  summary_pdf() a printable policy summary

Everything here is derived from the uploaded clauses; nothing is invented. Where the policy is silent, the answer says so.
"""
from __future__ import annotations

import html
import io
import re
import uuid
from datetime import date, datetime, timezone
from typing import Optional

import pymupdf

from app.adjudication.adjudicate import adjudicate, retriever_for
from app.models import Bill, Claim, ClaimFacts, ClauseCategory as Cat, DocumentRecord
from decimal import Decimal

from app.money import fmt as _fmt


def fmt(v) -> str:
    return _fmt(Decimal(str(v)))
from app.qa import indic
from app.qa.speech import explain, summarise

NOT_FOUND = "Not found in the provided documents"


# ------------------------------------------------------------------ estimate
def estimate(policy: DocumentRecord, docs: dict[str, DocumentRecord], bill: Bill, admission: date, discharge: Optional[date],
             diagnosis: str, facts: ClaimFacts, owner_id: str):
    claim = Claim(claim_id=f"est-{uuid.uuid4().hex[:8]}", title="Estimate", policy_document_id=policy.document_id,
                  endorsement_ids=[d.document_id for d in docs.values() if d.doc_type.value == "endorsement"], benefit_summary_ids=[],
                  bill=bill, admission_date=admission, discharge_date=discharge, diagnosis=diagnosis or NOT_FOUND, facts=facts,
                  synthetic=False, created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), owner_id=owner_id)
    a = adjudicate(claim, docs, cause="Estimate (not saved)")
    return claim, a


def _si(doc: DocumentRecord):
    v = (doc.metadata or {}).get("sum_insured")
    try:
        return Decimal(str(v).replace(",", "")) if v and NOT_FOUND not in str(v) else None
    except Exception:
        return None


# ------------------------------------------------------------------ ask
_DEF_PENALTY = {Cat.definition, Cat.applicability, Cat.precedence, Cat.computation_order}
_NONE = {"en": "Your policy doesn't seem to say anything about that. The closest clause is {sec} ({head}); open it to check.",
         "hi": "आपकी पॉलिसी में इस बारे में कुछ साफ़ नहीं लिखा है। सबसे नज़दीकी धारा {sec} ({head}) है; उसे खोलकर देख लें।"}
_ALSO = {"en": "Also relevant: ", "hi": "इससे जुड़ी धाराएँ: "}


def ask(doc: DocumentRecord, question: str) -> dict:
    q = question.strip()
    lang, routed = "en", q
    if indic.is_indic(q):
        lang, routed = "hi", indic.to_english(q)
    clauses = doc.clauses or []
    base = {"question": q, "language": lang, "engine": "Deterministic evidence engine", "kind": "policy",
            "disclaimer": "Estimates only. The policy wording governs; this is not an insurer decision."}
    if not clauses or not routed.strip():
        return base | {"answer": "Ask a question about this policy, for example: Is room rent capped?", "citations": [], "grounded": False}
    r = retriever_for(clauses)
    hits = r.search(routed, method="hybrid", k=6)
    bm = [h for h in r.search(routed, method="bm25", k=6) if h.score > 0]
    lexical = {h.clause_id for h in bm}
    strong = {h.clause_id for h in bm[:3] if bm and h.score >= bm[0].score * 0.5}
    ranked = [r.clauses[h.clause_id] for h in hits]
    # prefer substantive clauses (coverage, limits, exclusions…) over definitions and housekeeping
    ranked.sort(key=lambda c: (c.clause_id not in lexical, c.interpretation.category in _DEF_PENALTY))
    if not ranked:
        return base | {"answer": "I couldn't find anything in this policy about that.", "citations": [], "grounded": False}
    top = ranked[0]
    cite = lambda c: {"clause_id": c.clause_id, "section": c.section, "heading": c.heading, "page": c.page,  # noqa: E731
                      "document_id": c.document_id, "excerpt": c.text[:400]}
    if top.clause_id not in lexical:
        return base | {"answer": _NONE[lang].format(sec=top.section, head=top.heading), "citations": [cite(top)], "grounded": False,
                       "answer_en": _NONE["en"].format(sec=top.section, head=top.heading)}
    also = [c for c in ranked[1:3] if c.clause_id in strong]

    def compose(lg: str) -> str:
        text = explain(top, lg, _si(doc))
        for tail in (" This is a simplified summary", " यह केवल सरल सार है"):
            text = text.split(tail)[0].strip()
        if also:
            text += "\n\n" + _ALSO[lg] + "; ".join(f"{c.section} ({c.heading})" for c in also) + "."
        return text
    # answer_en: the read-aloud is always in English
    return base | {"answer": compose(lang), "answer_en": compose("en"), "citations": [cite(c) for c in [top, *also]], "grounded": True}


# ------------------------------------------------------------------ checklist
def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    return date(d.year + y, m + 1, min(d.day, 28))


def _parse(v) -> Optional[date]:
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def checklist(doc: DocumentRecord) -> dict:
    md = doc.metadata or {}
    start = _parse(md.get("continuous_coverage_since")) or _parse(md.get("policy_period_from")) or _parse(md.get("effective_date"))
    today = date.today()
    out: dict = {"policy_start": start.isoformat() if start else None, "claim_documents": [], "waits": [], "window": None,
                 "deductible": None, "copay": None, "notice": []}
    for c in doc.clauses or []:
        it = c.interpretation
        if it.category == Cat.claim_requirement:
            listing = next((x for x in re.split(r"(?<=[.;])\s+", c.text) if re.search(r"\b(?:includ|following|:)", x, re.I)), None)
            if listing:   # only a sentence that actually lists documents
                body = re.split(r"\b(?:include|includes|including|following|are)\b|:", listing, maxsplit=1)[-1]
                parts = [re.sub(r"^(?:and|the|a|an)\s+", "", p.strip(" .;"), flags=re.I) for p in re.split(r",|;|\band\b", body)]
                out["claim_documents"] += [{"text": p[:1].upper() + p[1:], "clause": c.section} for p in parts if 3 < len(p) < 120]
            if re.search(r"\bwithin\s+\d+\s+(?:days|hours)\b", c.text, re.I):
                out["notice"].append({"text": c.text, "clause": c.section})
        elif it.category == Cat.waiting_period and (it.waiting_months or it.waiting_days):
            ready = None
            if start:
                ready = _add_months(start, it.waiting_months) if it.waiting_months else date.fromordinal(start.toordinal() + (it.waiting_days or 0))
            label = ", ".join(it.scope_terms[:3]) if it.waiting_months else f"Illness in the first {it.waiting_days} days (accidents excepted)"
            out["waits"].append({"label": label[:1].upper() + label[1:], "months": it.waiting_months, "days": None if it.waiting_months else it.waiting_days,
                                 "covered_from": ready.isoformat() if ready else None, "done": bool(ready and ready <= today), "clause": c.section})
        elif it.category == Cat.time_window and not out["window"] and (it.window_days_before or it.window_days_after):
            out["window"] = {"before": it.window_days_before, "after": it.window_days_after, "clause": c.section}
        elif it.category == Cat.deductible and it.amount and not out["deductible"]:
            out["deductible"] = {"amount": f"{it.amount:.2f}", "clause": c.section}
        elif it.category == Cat.copayment and it.percent and not out["copay"]:
            out["copay"] = {"percent": f"{it.percent.normalize():f}", "clause": c.section}
    return out


# ------------------------------------------------------------------ summary PDF
CSS = """
body { font-family: sans-serif; font-size: 9.5pt; color: #222521; }
h1 { font-size: 20pt; color: #142d27; margin-bottom: 0; }
h2 { font-size: 12pt; color: #142d27; margin-top: 14pt; border-bottom: 1px solid #d3cab6; padding-bottom: 2pt; }
.muted { color: #6c7068; }
table { border-collapse: collapse; width: 100%; }
td { border-bottom: 1px solid #e3ddcf; padding: 4pt 3pt; vertical-align: top; }
.ref { color: #1f5a4a; font-family: monospace; font-size: 8pt; }
.key td { font-size: 11pt; }
"""


def _e(s) -> str:
    s = str(s).replace("–", "-").replace("—", "-").replace("→", "->").replace("₹", "INR ").replace("≤", "<=")
    return html.escape(s)


def summary_pdf(doc: DocumentRecord) -> bytes:
    md = doc.metadata or {}
    title = md.get("title") or doc.filename
    s = summarise(doc.clauses or [], title, "en", _si(doc))
    ck = checklist(doc)
    f = s.get("facts") or {}
    known = lambda v: v and NOT_FOUND not in str(v)  # noqa: E731
    parts = [f"<h1>{_e(title)}</h1><p class='muted'>Policy summary prepared by Nivaaran · {date.today().isoformat()}</p>", "<table>"]
    for k, v in (("Insurer", md.get("insurer")), ("Policy number", md.get("policy_number")),
                 ("Policy period", f"{md.get('policy_period_from')} to {md.get('policy_period_to')}" if known(md.get("policy_period_from")) else None),
                 ("Sum insured", f"INR {fmt(md['sum_insured'])}" if known(md.get("sum_insured")) else None)):
        if known(v):
            parts.append(f"<tr><td class='muted'>{_e(k)}</td><td>{_e(v)}</td></tr>")
    parts.append("</table><h2>Key numbers</h2><table class='key'>")
    if f.get("deductible"):
        parts.append(f"<tr><td>You pay first, each year</td><td><b>INR {fmt(f['deductible']['amount'])}</b> <span class='ref'>{f['deductible']['clause']}</span></td></tr>")
    if f.get("copay"):
        parts.append(f"<tr><td>Co-payment on each claim</td><td><b>{f['copay']['percent']}%</b> <span class='ref'>{f['copay']['clause']}</span></td></tr>")
    for l in f.get("limits", []):
        parts.append(f"<tr><td>{_e(l['label'].capitalize())}</td><td><b>up to INR {fmt(l['amount'])}</b> {_e(l['basis'])} <span class='ref'>{l['clause']}</span></td></tr>")
    if f.get("window"):
        w = f["window"]
        parts.append(f"<tr><td>Bills before and after a stay</td><td><b>{w['before']} days before, {w['after']} days after</b> <span class='ref'>{w['clause']}</span></td></tr>")
    parts.append("</table>")
    for sec in s["sections"]:
        parts.append(f"<h2>{_e(sec['heading'])}</h2><table>")
        parts += [f"<tr><td>{_e(i['text'][:1].upper() + i['text'][1:])}</td><td class='ref'>{_e(i['clause'])}</td></tr>" for i in sec["items"]]
        parts.append("</table>")
    if ck["waits"]:
        parts.append("<h2>Waiting periods and when they end</h2><table>")
        for w in ck["waits"]:
            when = f"covered from {w['covered_from']}" if w["covered_from"] else ""
            parts.append(f"<tr><td>{_e(w['label'])}</td><td>{w['months'] or w['days']} {'months' if w['months'] else 'days'} {_e(when)}</td><td class='ref'>{w['clause']}</td></tr>")
        parts.append("</table>")
    if ck["claim_documents"]:
        parts.append("<h2>Documents to keep for a claim</h2><table>")
        parts += [f"<tr><td>{_e(d['text'])}</td><td class='ref'>{d['clause']}</td></tr>" for d in ck["claim_documents"]]
        parts.append("</table>")
    parts.append("<p class='muted' style='margin-top:16pt'>This is a simplified summary generated from the policy's clauses. "
                 "The policy wording governs. Nivaaran is not an insurer and this is not a claim decision.</p>")
    story = pymupdf.Story(html="".join(parts), user_css=CSS)
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    media = pymupdf.paper_rect("a4")
    where = media + (44, 48, -44, -48)
    more = True
    while more:
        dev = writer.begin_page(media)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    return buf.getvalue()
