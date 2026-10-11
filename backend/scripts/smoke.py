"""Developer smoke run: ingest the synthetic demo documents and print the adjudication ledger."""
from pathlib import Path

from app.adjudication.adjudicate import adjudicate
from app.bills.parse import build_bill, parse_bill_bytes
from app.ingestion.documents import process_policy_document
from app.models import Claim, DocType
from app.money import fmt

D = Path(__file__).resolve().parent.parent / "demo" / "documents"
pol = process_policy_document((D / "synthetic_policy_v1.pdf").read_bytes(), "policy.pdf", DocType.policy)
end = process_policy_document((D / "synthetic_endorsement_E01.pdf").read_bytes(), "e01.pdf", DocType.endorsement)
bill = build_bill(parse_bill_bytes((D / "synthetic_bill_appendicectomy.pdf").read_bytes(), "pdf"), synthetic=True)
print("bill", bill.hospital, bill.admission_date, bill.discharge_date, len(bill.items), fmt(bill.computed_total), bill.issues)
docs = {pol.document_id: pol, end.document_id: end}
for eids in ([], [end.document_id]):
    claim = Claim(claim_id="c1", title="Laparoscopic appendicectomy", policy_document_id=pol.document_id, endorsement_ids=eids,
                  bill=bill, admission_date=bill.admission_date, discharge_date=bill.discharge_date, diagnosis=bill.diagnosis)
    a = adjudicate(claim, docs)
    print("\n== version:", a.version.selected.label, "|", a.version.reasons[0])
    for r in a.rows:
        print(f"{r.line_no:2d} {r.original_description[:34]:34s} {r.status:24s} claimed {fmt(r.claimed_amount):>10s} "
              f"pay {fmt(r.payable_low):>10s}-{fmt(r.payable_high):>10s} [{', '.join(c.split(':')[1] for c in r.supporting_clause_ids)}] q={r.evidence_quality}")
    s = a.summary
    print("payable", fmt(s.payable_low), "-", fmt(s.payable_high), "patient", fmt(s.patient_low), "-", fmt(s.patient_high))
    print("order", s.computation_order, "|", s.order_source)
    print("invariants failed:", [i for i in a.invariants if not i["passed"]])
    for t in a.trace_low:
        print("  ", t.step_no, t.stage, fmt(t.amount_before), "->", fmt(t.amount_after), "|", t.description)
