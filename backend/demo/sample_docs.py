"""A sample health insurance policy and a matching hospital bill, for testing Nivaaran with your own uploads.

Both are fictitious (the insurer, hospital, patient and amounts are invented) and say so in a small footer, but they are
laid out like real documents: a schedule with the key terms, numbered clauses, exclusions, waiting periods, cost sharing,
and an itemised bill whose lines exercise those rules. They are generated from the same clause content as the automated
test pack, so the results are known to work end to end.

Run from the backend directory:   python -m demo.sample_docs      (writes to ../sample-documents/)
"""
from __future__ import annotations

from pathlib import Path

import pymupdf as fitz

from demo import test_pack as P
from demo.generate_demo import MARGIN, PAGE_W, Writer, _render_clauses

OUT_DIR = Path(__file__).resolve().parents[2] / "sample-documents"
POLICY_NO = "AKF-2026-004517"
FOOTER = "Sample document for testing Nivaaran - fictitious insurer"

POLICY_HEADER = [
    "Arogya Kavach Family Floater - Policy Wording (Version 2.0)",
    "Insurer: Suraksha General Insurance Co. Ltd. (sample)",
    f"Policy Number: {POLICY_NO}",
    "Policyholder: Riya Sharma",
    "Policy Period: 01-Jan-2026 to 31-Dec-2026",
    "Policy Effective Date: 01-Jan-2026",
    "Continuous Coverage Since: 01-Jan-2023",
    "Sum Insured: INR 5,00,000",
]

# Same clauses as the test pack, with this policy's own figures (sum insured 5 lakh, room 1% = 5,000/day, 10% co-pay).
REPLACE = {
    "ICU charges are payable up to INR 8,000 per day.": "ICU charges are payable up to INR 10,000 per day.",
    "An aggregate deductible of INR 15,000 applies per policy year": "An aggregate deductible of INR 10,000 applies per policy year",
    "A co-payment of 20% applies": "A co-payment of 10% applies",
}


def _policy_pages():
    pages = []
    for page in P.POLICY_PAGES:
        out = []
        for heading, body in page:
            if body:
                for a, b in REPLACE.items():
                    body = body.replace(a, b)
            out.append((heading, body))
        pages.append(out)
    return pages


BILL_HEADER = [
    "City Care Hospital - Itemised Final Bill",
    "Bill Number: CCH-2026-20417",
    "Patient: Riya Sharma",
    f"Policy Number: {POLICY_NO}",
    "Bill Date: 30-Apr-2026",
    "Admission Date: 10-Mar-2026",
    "Discharge Date: 14-Mar-2026",
    "Diagnosis: Coronary artery disease (single vessel)",
    "Procedure: Coronary angioplasty with one drug-eluting stent",
]


def _render_bill(path: Path) -> None:
    doc = fitz.open()
    w = Writer(doc, 1, banner="", footer="Sample hospital bill for testing Nivaaran - fictitious hospital")
    w.new_page()
    w.line(BILL_HEADER[0], font="hebo", size=13, gap=6)
    for h in BILL_HEADER[1:]:
        w.line(h, size=10)
    w.space(10)
    cols = [MARGIN, MARGIN + 22, MARGIN + 238, MARGIN + 312, MARGIN + 350, MARGIN + 420]
    for x, h in zip(cols, ["No", "Description", "Date", "Qty", "Rate (INR)", "Amount (INR)"]):
        w.page.insert_text((x, w.y + 10), h, fontname="hebo", fontsize=9)
    w.y += 16
    w.page.draw_line((MARGIN, w.y - 3), (PAGE_W - MARGIN, w.y - 3), color=(0.6, 0.6, 0.6), width=0.6)
    for i, (desc, dt, qty, rate, amt, _) in enumerate(P.BILL_ITEMS, start=1):
        for x, v in zip(cols, [str(i), desc, dt, qty, rate, amt]):
            w.page.insert_text((x, w.y + 10), v, fontname="helv", fontsize=9)
        w.y += 15
    w.page.draw_line((MARGIN, w.y + 2), (PAGE_W - MARGIN, w.y + 2), color=(0.6, 0.6, 0.6), width=0.6)
    w.y += 8
    w.page.insert_text((cols[1], w.y + 10), "Total Amount", fontname="hebo", fontsize=10)
    w.page.insert_text((cols[5], w.y + 10), P._inr(P.BILL_TOTAL_INT), fontname="hebo", fontsize=10)
    doc.set_metadata({"title": BILL_HEADER[0], "subject": "Sample hospital bill", "creator": "Nivaaran document generator"})
    doc.save(path)
    doc.close()


def generate(out_dir: Path = OUT_DIR) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"policy": out_dir / "Sample_Health_Insurance_Policy.pdf", "bill": out_dir / "Sample_Hospital_Bill.pdf"}
    _render_clauses(paths["policy"], POLICY_HEADER, _policy_pages(), banner="", footer=FOOTER, subject="Sample health insurance policy")
    _render_bill(paths["bill"])
    return paths


if __name__ == "__main__":
    for k, p in generate().items():
        print(f"{k:8s} {p}")
