"""A second, fuller SYNTHETIC test pack: a policy that exercises every rule Nivaaran's engine evaluates, a matching
hospital bill whose lines each trigger one of those rules, two endorsements (one in force, one future-dated) and a
brochure with deliberate mismatches.

Everything here is fictitious: the insurer, hospital, patient, policy number and all amounts are invented for testing.

Run from the backend directory:
    python -m demo.test_pack            # writes the PDFs to ../test-pack/
    python -m demo.test_pack --verify   # also runs them through the real API and writes ../test-pack/TEST_GUIDE.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import pymupdf as fitz

from demo.generate_demo import MARGIN, PAGE_W, Writer, _render_clauses

OUT_DIR = Path(__file__).resolve().parents[2] / "test-pack"

POLICY_NO = "TST-AK-2026-000456"
INSURER = "Insurer: Suraksha Demo General Insurance Ltd. (fictitious)"

POLICY_HEADER = [
    "Arogya Kavach Family Floater - Policy Wording (Version 2.0)",
    INSURER,
    f"Policy Number: {POLICY_NO}",
    "Policyholder: Test Policyholder B (synthetic)",
    "Policy Period: 01-Jan-2026 to 31-Dec-2026",
    "Policy Effective Date: 01-Jan-2026",
    "Continuous Coverage Since: 01-Jan-2023",
    "Sum Insured: INR 2,00,000",
]

POLICY_PAGES = [
    [
        ("Section 1 Definitions", None),
        ("1.1 Hospitalisation", "Hospitalisation means admission in a hospital for a minimum period of 24 consecutive in-patient care hours."),
        ("1.2 Day Care Treatment", "Day care treatment means a medical or surgical procedure undertaken under general or local anaesthesia in a hospital in less than 24 hours because of technological advancement."),
        ("1.3 Non-Medical Items", "Non-medical items means items that are not directly related to medical treatment and that are listed in Annexure II."),
        ("1.4 Medically Necessary", "Medically necessary means treatment that is required for the medical management of the illness or injury suffered by the insured."),
        ("Section 2 Coverage", None),
        ("2.1 In-patient Hospitalisation Expenses", "The Company will pay medically necessary expenses incurred during hospitalisation for room, boarding and nursing, operation theatre charges, and surgical procedures, subject to the limits in this policy."),
        ("2.2 Room Rent Limit", "Room rent, boarding and nursing charges are payable up to 1% of the sum insured per day. Room charges above this limit are not payable. No proportionate deduction is applied to other expenses."),
        ("2.3 Intensive Care Unit Charges", "ICU charges are payable up to INR 8,000 per day."),
        ("2.4 Professional Fees", "Fees of surgeons, cardiologists, anaesthetists, and consulting doctors attending the insured during hospitalisation are payable."),
    ],
    [
        ("2.5 Diagnostic Investigations", "Laboratory investigations, pathology tests, blood tests, ECG, echocardiography, and imaging including X-ray, ultrasonography, CT and MRI performed during hospitalisation are payable."),
        ("2.6 Medicines and Drugs", "Medicines, drugs, injections and intravenous fluids administered during hospitalisation are payable."),
        ("2.7 Pre- and Post-Hospitalisation Expenses", "Medical expenses incurred up to 60 days before admission and up to 90 days after discharge for the same condition, including consultations, investigations and physiotherapy, are payable."),
        ("2.8 Road Ambulance", "Road ambulance charges are payable up to INR 2,500 per hospitalisation."),
        ("2.9 Surgical Implants", "Surgically implanted devices such as stents, valves and pacemakers are payable provided the implant invoice and barcode sticker are submitted with the claim."),
        ("2.10 Cardiac Procedures", "Coronary angiography, coronary angioplasty and cath lab charges are payable."),
        ("2.11 Physiotherapy", "Physiotherapy prescribed for the condition requiring hospitalisation is payable up to INR 5,000 per hospitalisation."),
        ("2.12 Day Care Procedures", "Day care treatment listed in the schedule of day care procedures is payable."),
        ("2.13 Modern Treatment Methods", "Robotic surgery and stereotactic radiosurgery are payable up to 25% of the sum insured per policy year."),
    ],
    [
        ("Section 3 Waiting Periods", None),
        ("3.1 Initial Waiting Period", "Any illness contracted within 30 days of the first policy commencement date is not payable, except treatment arising from an accident."),
        ("3.2 Specific Disease Waiting Period", "Treatment of cataract, hernia, kidney stones and joint replacement is payable only after 24 months of continuous coverage."),
        ("3.3 Pre-existing Diseases", "Pre-existing diseases are payable only after 36 months of continuous coverage."),
        ("Section 4 Exclusions", None),
        ("4.1 Non-Medical Items and Consumables", "Non-medical items and consumables listed in Annexure II, including disposable gloves, masks, syringes, admission kits and toiletries, are not payable."),
        ("4.2 Vitamins and Supplements", "Vitamins, multivitamin injections, tonics and nutritional supplements are not payable unless prescribed by the treating doctor as part of the treatment for the condition requiring hospitalisation."),
        ("4.3 Comfort and Personal Charges", "Television, telephone, laundry, attendant charges and guest meals are not payable."),
        ("4.4 Cosmetic Treatment", "Cosmetic or aesthetic treatment is not payable unless required to treat an injury."),
        ("4.5 Substance Abuse", "Treatment arising from alcohol or drug abuse is not payable."),
        ("4.6 Experimental Treatment", "Experimental, investigational or unproven treatment is not payable."),
    ],
    [
        ("Section 5 Cost Sharing", None),
        ("5.1 Deductible", "An aggregate deductible of INR 15,000 applies per policy year to the total admissible claim amount."),
        ("5.2 Co-payment", "A co-payment of 20% applies to the admissible claim amount after the deductible."),
        ("5.3 Order of Computation", "The admissible amount is computed in the following order: (a) exclusions and non-payable items are removed; (b) item limits and sub-limits are applied; (c) the deductible is applied; (d) the co-payment is applied; (e) the result is limited to the available sum insured."),
        ("Section 6 Claims", None),
        ("6.1 Claim Documents", "Claim documents must include the discharge summary, the itemised final bill, prescriptions, investigation reports, and implant invoices where applicable."),
        ("6.2 Claim Intimation", "Claim documents must be submitted within 30 days of discharge."),
        ("Section 7 General Conditions", None),
        ("7.1 Interpretation of Specific Exclusions", "Where a specific exclusion applies to an item, it prevails over general coverage clauses unless an endorsement expressly provides otherwise."),
        ("7.2 Endorsements", "Endorsements apply only to hospitalisations commencing on or after the endorsement effective date and do not apply retrospectively."),
    ],
    [
        ("Annexure II List of Non-Payable Items", None),
        ("A2.1 Toiletries and Personal Care", "Toiletries, admission kits, soap, toothpaste and similar personal care items are not payable."),
        ("A2.2 Disposable Protective Items", "Disposable gloves, masks, aprons and caps are not payable."),
        ("A2.3 Disposables", "Syringes, needles, cotton, gauze and ECG electrodes are not payable."),
        ("A2.4 Guest Services", "Attendant food, guest meals and visitor passes are not payable."),
    ],
]

ENDORSEMENT_HEADER = [
    f"Endorsement No. A-01 to Policy {POLICY_NO}",
    INSURER,
    f"Policy Number: {POLICY_NO}",
    "Endorsement Issue Date: 20-Jan-2026",
    "Endorsement Effective Date: 01-Feb-2026",
    "Applies To: Hospitalisations commencing on or after 01-Feb-2026",
]
ENDORSEMENT_PAGES = [[
    ("Endorsement Provisions", None),
    ("E1.1 Revised Room Rent Limit", "This endorsement replaces clause 2.2. Room rent, boarding and nursing charges are payable up to INR 5,000 per day. Room charges above this limit are not payable. No proportionate deduction is applied to other expenses."),
    ("E1.2 Revised Co-payment", "This endorsement replaces clause 5.2. A co-payment of 10% applies to the admissible claim amount after the deductible."),
    ("E1.3 Consumables Cover", "Notwithstanding clause 4.1 and Annexure II, disposable gloves, masks and syringes used during hospitalisation are payable up to INR 3,000 per hospitalisation."),
]]

FUTURE_HEADER = [
    f"Endorsement No. A-02 to Policy {POLICY_NO}",
    INSURER,
    f"Policy Number: {POLICY_NO}",
    "Endorsement Issue Date: 15-May-2026",
    "Endorsement Effective Date: 01-Jun-2026",
    "Applies To: Hospitalisations commencing on or after 01-Jun-2026",
]
FUTURE_PAGES = [[
    ("Endorsement Provisions", None),
    ("E2.1 Revised ICU Limit", "This endorsement replaces clause 2.3. ICU charges are payable up to INR 12,000 per day."),
]]

BROCHURE_HEADER = [
    "Arogya Kavach Family Floater - Benefits at a Glance (Brochure)",
    INSURER,
    f"Policy Number: {POLICY_NO}",
    "Policy Period: 01-Jan-2026 to 31-Dec-2026",
    "Sum Insured: INR 2,00,000",
]
# Deliberate mismatches for the Mismatch checks: room rent and deductible are misstated; ambulance and co-payment match
# the endorsed policy; physiotherapy omits its cap.
BROCHURE_PAGES = [[
    ("Key Benefits", None),
    ("S1.1 Room Rent", "Room rent, boarding and nursing charges are payable up to INR 8,000 per day."),
    ("S1.2 Co-payment", "A co-payment of 10% applies to the admissible claim amount after the deductible."),
    ("S1.3 Road Ambulance", "Road ambulance charges are payable up to INR 2,500 per hospitalisation."),
    ("S1.4 Deductible", "An aggregate deductible of INR 10,000 applies per policy year to the total admissible claim amount."),
    ("S1.5 Physiotherapy", "Physiotherapy prescribed for the condition requiring hospitalisation is payable."),
]]

BILL_HEADER = [
    "Demo Heart & Multispeciality Hospital (fictitious) - Itemised Final Bill",
    "Bill Number: DHMH-TST-20417",
    "Patient: Test Policyholder B (synthetic)",
    f"Policy Number: {POLICY_NO}",
    "Bill Date: 30-Apr-2026",
    "Admission Date: 10-Mar-2026",
    "Discharge Date: 14-Mar-2026",
    "Diagnosis: Coronary artery disease (single vessel)",
    "Procedure: Coronary angioplasty with one drug-eluting stent",
]

# (description, service date, qty, unit rate, amount, what the line is designed to test)
BILL_ITEMS = [
    ("Private Room Charges", "10-03-2026", "2", "7,000.00", "14,000.00", "Room rent above the endorsed per-day limit (E1.1 replaces 2.2)"),
    ("ICU Charges", "11-03-2026", "2", "10,000.00", "20,000.00", "Per-day ICU limit (2.3); the future endorsement A-02 must NOT apply"),
    ("Cath Lab Charges", "11-03-2026", "1", "45,000.00", "45,000.00", "Specific procedure coverage (2.10)"),
    ("Interventional Cardiologist Fee", "11-03-2026", "1", "60,000.00", "60,000.00", "Professional fees (2.4)"),
    ("Anaesthetist Fee", "11-03-2026", "1", "8,000.00", "8,000.00", "Professional fees (2.4)"),
    ("Drug Eluting Stent (implant)", "11-03-2026", "1", "1,10,000.00", "1,10,000.00", "Conditional coverage: needs the implant invoice (2.9)"),
    ("Coronary Angiography", "10-03-2026", "1", "15,000.00", "15,000.00", "Specific procedure coverage (2.10)"),
    ("ECG and 2D Echo", "20-02-2026", "1", "4,500.00", "4,500.00", "Pre-hospitalisation, 18 days before admission: inside the 60-day window (2.7)"),
    ("Cardiology Consultation", "02-01-2026", "1", "1,500.00", "1,500.00", "Pre-hospitalisation, 67 days before admission: outside the 60-day window (2.7)"),
    ("Blood tests - Lipid, Troponin, CBC", "10-03-2026", "1", "5,200.00", "5,200.00", "Diagnostic investigations (2.5)"),
    ("Inj. Heparin and IV fluids", "11-03-2026", "1", "9,800.00", "9,800.00", "Medicines and drugs (2.6)"),
    ("Multivitamin injection", "12-03-2026", "3", "600.00", "1,800.00", "Conditional exclusion: payable only if prescribed (4.2)"),
    ("Disposable gloves, masks & syringes", "11-03-2026", "1", "4,200.00", "4,200.00", "Excluded (4.1) but overridden by 'Notwithstanding' E1.3, capped at INR 3,000"),
    ("ECG electrodes & cotton", "11-03-2026", "1", "900.00", "900.00", "Annexure exclusion (A2.3) with no override"),
    ("Admission kit & toiletries", "10-03-2026", "1", "1,500.00", "1,500.00", "Exclusion (4.1 / A2.1)"),
    ("Attendant food & guest meals", "10-03-2026", "4", "450.00", "1,800.00", "Comfort and guest exclusions (4.3 / A2.4)"),
    ("Television charges", "10-03-2026", "4", "250.00", "1,000.00", "Comfort exclusion (4.3)"),
    ("Ambulance (home to hospital)", "10-03-2026", "1", "3,500.00", "3,500.00", "Per-hospitalisation ambulance limit (2.8)"),
    ("Cardiac rehab physiotherapy", "28-03-2026", "4", "1,500.00", "6,000.00", "Post-hospitalisation (14 days after discharge) plus the physiotherapy cap (2.7, 2.11)"),
    ("Follow-up cardiology consultation", "30-04-2026", "1", "1,500.00", "1,500.00", "Post-hospitalisation, 47 days after discharge: inside the 90-day window (2.7)"),
    ("Medical records & file charges", "14-03-2026", "1", "500.00", "500.00", "No clause mentions it: should stay unresolved, not guessed"),
    ("Dietitian consultation", "13-03-2026", "1", "800.00", "800.00", "No clause mentions it: should stay unresolved, not guessed"),
]


def _amount(s: str) -> int:
    return int(float(s.replace(",", "")))


BILL_TOTAL_INT = sum(_amount(i[4]) for i in BILL_ITEMS)


def _inr(n: int) -> str:
    s = str(n)
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return (",".join(groups) + "," if groups else "") + tail + ".00"


def _render_bill(path: Path) -> None:
    doc = fitz.open()
    w = Writer(doc, 1)
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
    for i, (desc, dt, qty, rate, amt, _) in enumerate(BILL_ITEMS, start=1):
        for x, v in zip(cols, [str(i), desc, dt, qty, rate, amt]):
            w.page.insert_text((x, w.y + 10), v, fontname="helv", fontsize=9)
        w.y += 15
    w.page.draw_line((MARGIN, w.y + 2), (PAGE_W - MARGIN, w.y + 2), color=(0.6, 0.6, 0.6), width=0.6)
    w.y += 8
    w.page.insert_text((cols[1], w.y + 10), "Total Amount", fontname="hebo", fontsize=10)
    w.page.insert_text((cols[5], w.y + 10), _inr(BILL_TOTAL_INT), fontname="hebo", fontsize=10)
    w.y += 30
    w.line("All amounts are illustrative synthetic values created for testing Nivaaran.", size=8.5, color=(0.4, 0.4, 0.4))
    doc.set_metadata({"title": BILL_HEADER[0], "subject": "SYNTHETIC test bill", "creator": "Nivaaran test pack"})
    doc.save(path)
    doc.close()


FILES = {
    "policy": "1_policy_arogya_kavach.pdf",
    "endorsement": "2_endorsement_A01_in_force.pdf",
    "future": "3_endorsement_A02_future_dated.pdf",
    "brochure": "4_brochure_benefits_at_a_glance.pdf",
    "bill": "5_hospital_bill_angioplasty.pdf",
}


def generate(out_dir: Path = OUT_DIR) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {k: out_dir / v for k, v in FILES.items()}
    _render_clauses(paths["policy"], POLICY_HEADER, POLICY_PAGES)
    _render_clauses(paths["endorsement"], ENDORSEMENT_HEADER, ENDORSEMENT_PAGES)
    _render_clauses(paths["future"], FUTURE_HEADER, FUTURE_PAGES)
    _render_clauses(paths["brochure"], BROCHURE_HEADER, BROCHURE_PAGES)
    _render_bill(paths["bill"])
    return paths


if __name__ == "__main__":
    for k, p in generate().items():
        print(f"{k:12s} {p}")
    if "--verify" in sys.argv:
        from demo.test_pack_verify import run
        run(OUT_DIR)
