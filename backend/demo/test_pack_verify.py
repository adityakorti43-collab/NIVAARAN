"""Run the SYNTHETIC test pack through the real HTTP API (in an isolated temporary database) and write TEST_GUIDE.md
with the results Nivaaran actually produced. Nothing in the guide is typed in by hand."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _fmt(v) -> str:
    if v is None:
        return "—"
    n = float(v)
    s = f"{abs(n):,.2f}"
    # Indian digit grouping
    whole, frac = s.split(".")
    whole = whole.replace(",", "")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:]); head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return ("−" if n < 0 else "") + "₹" + whole + "." + frac


STATUS = {"potentially_covered": "Covered", "partially_payable": "Partly payable", "potentially_excluded": "Excluded",
          "conditional": "Conditional", "insufficient_evidence": "No evidence", "conflicting_evidence": "Conflicting evidence",
          "manual_review_required": "Needs review"}


def run(out_dir: Path) -> Path:
    os.environ["NIVAARAN_DATA_DIR"] = tempfile.mkdtemp(prefix="nivaaran-testpack-")
    from fastapi.testclient import TestClient
    from app.main import app
    from demo import test_pack as P

    c = TestClient(app)
    r = c.post("/api/auth/register", json={"email": "tester@example.com", "name": "Test Policyholder B", "password": "test pack 2026"})
    assert r.status_code == 200, r.text

    def up(key: str, doc_type: str) -> dict:
        f = out_dir / P.FILES[key]
        res = c.post("/api/documents", files={"file": (f.name, f.read_bytes(), "application/pdf")}, data={"doc_type": doc_type})
        assert res.status_code == 200, res.text
        return res.json()

    pol, a01, a02, bro = up("policy", "policy"), up("endorsement", "endorsement"), up("future", "endorsement"), up("brochure", "benefit_summary")
    billf = out_dir / P.FILES["bill"]
    bill = c.post("/api/bills/parse", files={"file": (billf.name, billf.read_bytes(), "application/pdf")}).json()
    bill = bill.get("bill", bill)
    created = c.post("/api/claims", json={
        "title": "Test pack: coronary angioplasty (SYNTHETIC)", "policy_document_id": pol["document_id"],
        "endorsement_ids": [a01["document_id"], a02["document_id"]], "benefit_summary_ids": [bro["document_id"]],
        "bill": bill, "admission_date": "2026-03-10", "discharge_date": "2026-03-14",
        "diagnosis": "Coronary artery disease (single vessel)"}).json()
    claim_id, a = created["claim"]["claim_id"], created["analysis"]

    # Second run: the user confirms the implant invoice and the vitamin prescription were submitted.
    facts = {**created["claim"]["facts"], "implant_invoice_submitted": "yes", "vitamin_prescription": "yes"}
    b = c.patch(f"/api/claims/{claim_id}", json={"facts": facts}).json()["analysis"]

    fair = c.get(f"/api/claims/{claim_id}/fairness").json()
    summ = {lang: c.get(f"/api/documents/{pol['document_id']}/summary", params={"lang": lang}).json() for lang in ("en", "hi", "mr")}
    qs = ["Why was the room charge reduced?", "Is the stent covered?", "How much will I have to pay myself?",
          "क्या आईसीयू का पूरा खर्च मिलेगा?", "माझ्या खिशातून किती पैसे जातील?"]
    answers = [(q, c.post(f"/api/claims/{claim_id}/ask", json={"question": q}).json()) for q in qs]

    design = {i + 1: item[5] for i, item in enumerate(P.BILL_ITEMS)}
    rows_b = {r["line_no"]: r for r in b["rows"]}
    s, sb = a["summary"], b["summary"]
    L: list[str] = []
    w = L.append
    w("# Nivaaran test pack: Arogya Kavach (SYNTHETIC)\n")
    w("Everything here is fictitious and made up for testing: the insurer, hospital, patient, policy number and every amount.\n")
    w("The results below were produced by running these exact files through Nivaaran's API "
      "(`python -m demo.test_pack --verify`); nothing in the tables is typed by hand.\n")
    w("## Files\n")
    w("| File | Upload as | What it is |\n|---|---|---|")
    w(f"| `{P.FILES['policy']}` | Policy wording | 37 clauses: definitions, coverage, % of sum-insured and rupee limits, pre/post-hospitalisation windows, three waiting periods, exclusions (plain and conditional), deductible, co-payment, order of computation, claim requirements, precedence, Annexure II |")
    w(f"| `{P.FILES['endorsement']}` | Endorsement | A-01, effective 01-Feb-2026: replaces room rent (2.2) and co-payment (5.2); a 'Notwithstanding' clause overrides the consumables exclusion with a cap |")
    w(f"| `{P.FILES['future']}` | Endorsement | A-02, effective 01-Jun-2026 (after the treatment): raises the ICU limit. It must be ignored for this claim |")
    w(f"| `{P.FILES['brochure']}` | Benefits brochure | 'Benefits at a glance' with deliberate mismatches: room rent and deductible are misstated; physiotherapy omits its cap |")
    w(f"| `{P.FILES['bill']}` | Hospital bill (on Claim workspace → New claim) | 22 lines, total {_fmt(P.BILL_TOTAL_INT)}; admitted 10-Mar-2026, discharged 14-Mar-2026 |")
    w("\n## How to test it on the website\n")
    w("1. **Documents** → upload the policy as *Policy wording*, both endorsements as *Endorsement / amendment*, and the brochure as *Benefits brochure*.")
    w("2. **Claim workspace → New claim** → choose the Arogya Kavach policy, tick both endorsements and the brochure, upload the bill, "
      "admission date **10-03-2026**, discharge **14-03-2026**, then analyse.")
    w("3. Compare what you see with the tables below. Then try the extras at the end (claim facts, What-if, Assistant, read-aloud).\n")

    w("## 1. Policy version chosen\n")
    sel = a["version"]["selected"]
    w(f"- Selected: **{sel['label'] if sel else 'none'}**")
    w(f"- Why: {' '.join(a['version'].get('reasons', [])) or '—'}")
    w("- Designed outcome: A-01 applies (effective before admission); A-02 is ignored (effective after admission).\n")

    w("## 2. Line by line (first analysis: implant invoice and vitamin prescription not yet confirmed)\n")
    w("| # | Bill line | Billed | Designed to test | Nivaaran says | Eligible | Est. payable | Clauses |\n|---|---|---|---|---|---|---|---|")
    for r in a["rows"]:
        w(f"| {r['line_no']} | {r['original_description']} | {_fmt(r['claimed_amount'])} | {design.get(r['line_no'], '')} | "
          f"**{STATUS.get(r['status'], r['status'])}** | {_fmt(r['eligible_amount'])} | {_fmt(r['payable_low'])} | "
          f"{', '.join(x.split(':')[-1] for x in r['supporting_clause_ids']) or '—'} |")

    w("\n## 3. Claim-level checks\n")
    for ck in a["claim_checks"]:
        w(f"- **{ck['check']}**: {ck['status'].replace('_', ' ')}. {ck['detail']}")

    w("\n## 4. The calculation\n")
    w(f"Order used: {' → '.join(s['computation_order'])} (source: {s['order_source']}).\n")
    w("| | First analysis | After confirming implant invoice + vitamin prescription |\n|---|---|---|")
    for k, label in [("total_billed", "Total billed"), ("eligible_definite", "Eligible (definite)"), ("item_reductions", "Removed by exclusions and item limits"),
                     ("deductible_applied_low", "Deductible applied"), ("copay_low", "Co-payment"), ("payable_low", "**Estimated payable (definite)**"),
                     ("payable_high", "Payable if all unresolved items go your way"), ("patient_low", "Your share (minimum)"), ("unresolved_exposure", "Still unresolved")]:
        w(f"| {label} | {_fmt(s[k])} | {_fmt(sb[k])} |")
    cap_a = [t for t in a["trace_low"] if t["stage"] == "sum_insured_cap"]
    cap_b = [t for t in b["trace_low"] if t["stage"] == "sum_insured_cap"]
    for nm, cap in (("First analysis", cap_a), ("After confirmation", cap_b)):
        if cap:
            w(f"\n{nm}, sum-insured cap step: {cap[0].get('note') or cap[0].get('explanation') or ''} ({_fmt(cap[0].get('amount_before'))} → {_fmt(cap[0].get('amount_after'))})")
    changed = [(n, a_r, rows_b[n]) for n, a_r in ((r["line_no"], r) for r in a["rows"]) if a_r["status"] != rows_b[n]["status"]]
    if changed:
        w("\nLines that changed after confirming the facts:\n")
        for n, x, y in changed:
            w(f"- Line {n} {x['original_description']}: {STATUS.get(x['status'])} → **{STATUS.get(y['status'])}**, payable {_fmt(x['payable_low'])} → {_fmt(y['payable_low'])}")

    w("\n## 5. Mismatch checks (brochure vs policy)\n")
    w(f"Status: **{fair.get('status_label')}**\n")
    for f in fair.get("findings", [])[:12]:
        w(f"- {f['title']} ({f.get('severity', '')} severity)")

    w("\n## 6. Read-aloud summaries\n")
    for lang, name in (("en", "English"), ("hi", "Hindi"), ("mr", "Marathi")):
        heads = ", ".join(f"{x['heading']} ({len(x['items'])})" for x in summ[lang]["sections"])
        w(f"- {name}: {heads}")

    w("\n## 7. Questions to try in the Assistant\n")
    for q, ans in answers:
        first = ans["answer"].replace("\n\n", " ").replace("\n", " ")
        w(f"- **{q}** → {'grounded' if ans.get('grounded') else 'not established'}: {first[:260]}{'…' if len(first) > 260 else ''}")

    w("\n## 8. More things to try\n")
    w("- **Claim facts**: set *Implant invoice submitted* and *Vitamin prescription* to Yes and watch lines 6 and 12 change (section 4).")
    w("- **What-if calculator**: change the room to a ₹5,000 room, remove the TV line, or switch the version to 'base policy only' to see the 1%-of-sum-insured room limit apply.")
    w("- **Documents → Listen to this policy**: hear the summary in English, हिंदी or मराठी.")
    w("- **Next steps**: draft a clarification letter about the brochure mismatch.")
    w("- **Reports**: download the PDF and JSON evidence report.\n")
    guide = out_dir / "TEST_GUIDE.md"
    guide.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote", guide)
    return guide
