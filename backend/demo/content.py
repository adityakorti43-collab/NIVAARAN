"""Source text for the SYNTHETIC demonstration package.

Every document is fictitious. The insurer, hospital, policyholder and all amounts are invented for
demonstration and do not represent any real insurer, product or price.
"""

BANNER = "SYNTHETIC DEMONSTRATION DOCUMENT - NOT A REAL INSURANCE POLICY OR BILL"

POLICY_HEADER = [
    "Sahaay Secure Health Plan - Policy Wording (Version 1.0)",
    "Insurer: Kalpavriksha Demo Insurance Co. (fictitious)",
    "Policy Number: SYN-HP-2025-000123",
    "Policyholder: Demo Policyholder A (synthetic)",
    "Policy Period: 01-Apr-2025 to 31-Mar-2026",
    "Policy Effective Date: 01-Apr-2025",
    "Continuous Coverage Since: 01-Apr-2022",
    "Sum Insured: INR 5,00,000",
]

# Each page is a list of (section heading line, body). Headings use the "N.N Title" convention.
POLICY_PAGES = [
    [
        ("Section 1 Definitions", None),
        ("1.1 Hospitalisation", "Hospitalisation means admission in a hospital for a minimum period of 24 consecutive in-patient care hours."),
        ("1.2 Non-Medical Items", "Non-medical items means items that are not directly related to medical treatment and that are listed in Annexure I."),
        ("1.3 Reasonable and Customary Charges", "Reasonable and customary charges means charges consistent with the prevailing charges in the geographical area for similar services."),
        ("Section 2 Coverage", None),
        ("2.1 In-patient Hospitalisation Expenses", "The Company will pay medically necessary expenses incurred during hospitalisation for room, boarding and nursing, operation theatre charges, and surgical procedures, subject to the limits in this policy."),
        ("2.2 Room Rent Limit", "Room rent, boarding and nursing charges are payable up to INR 5,000 per day. Room charges above this limit are not payable. No proportionate deduction is applied to other expenses."),
        ("2.3 Intensive Care Unit Charges", "ICU charges are payable up to INR 10,000 per day."),
    ],
    [
        ("2.4 Professional Fees", "Fees of surgeons, anaesthetists, and consulting doctors attending the insured during hospitalisation are payable."),
        ("2.5 Diagnostic Investigations", "Laboratory investigations, pathology tests, and imaging including X-ray, ultrasonography, CT and MRI performed during hospitalisation are payable."),
        ("2.6 Medicines and Drugs", "Medicines, drugs and intravenous fluids administered during hospitalisation are payable."),
        ("2.7 Pre- and Post-Hospitalisation Expenses", "Medical expenses incurred up to 30 days before admission and up to 60 days after discharge for the same condition, including follow-up consultations and investigations, are payable."),
        ("2.8 Road Ambulance", "Road ambulance charges are payable up to INR 2,000 per hospitalisation."),
        ("2.9 Cataract Surgery", "Cataract surgery is payable up to INR 40,000 per eye."),
        ("2.10 Respiratory Therapy", "Respiratory therapy during hospitalisation, including nebulisation and nebulizer kits used for in-patient care, is payable."),
        ("2.11 Surgical Implants", "Surgically implanted devices such as stents and meshes are payable provided the implant invoice and barcode sticker are submitted with the claim."),
    ],
    [
        ("Section 3 Waiting Periods", None),
        ("3.1 Initial Waiting Period", "Any illness contracted within 30 days of the first policy commencement date is not payable, except treatment arising from an accident."),
        ("3.2 Specific Disease Waiting Period", "Treatment of cataract, hernia and joint replacement is payable only after 24 months of continuous coverage."),
        ("3.3 Pre-existing Diseases", "Pre-existing diseases are payable only after 48 months of continuous coverage."),
        ("Section 4 Exclusions", None),
        ("4.1 Non-Medical Items and Consumables", "Non-medical items and consumables listed in Annexure I, including disposable gloves, masks, syringes, admission kits and toiletries, are not payable."),
        ("4.2 Vitamins and Supplements", "Vitamins, tonics and nutritional supplements are not payable unless prescribed by the treating doctor as part of the treatment for the condition requiring hospitalisation."),
        ("4.3 Comfort and Personal Charges", "Television, telephone, laundry and attendant charges are not payable."),
        ("4.4 Cosmetic Treatment", "Cosmetic or aesthetic treatment is not payable unless required to treat an injury."),
    ],
    [
        ("Section 5 Cost Sharing", None),
        ("5.1 Deductible", "An aggregate deductible of INR 10,000 applies per policy year to the total admissible claim amount."),
        ("5.2 Co-payment", "A co-payment of 10% applies to the admissible claim amount after the deductible."),
        ("5.3 Order of Computation", "The admissible amount is computed in the following order: (a) exclusions and non-payable items are removed; (b) item limits and sub-limits are applied; (c) the deductible is applied; (d) the co-payment is applied; (e) the result is limited to the available sum insured."),
        ("Section 6 Claims", None),
        ("6.1 Claim Documents", "Claim documents must include the discharge summary, the itemised final bill, prescriptions, investigation reports, and implant invoices where applicable."),
        ("Section 7 General Conditions", None),
        ("7.1 Interpretation of Specific Exclusions", "Where a specific exclusion applies to an item, it prevails over general coverage clauses unless an endorsement expressly provides otherwise."),
        ("7.2 Endorsements", "Endorsements apply only to hospitalisations commencing on or after the endorsement effective date and do not apply retrospectively."),
    ],
    [
        ("Annexure I List of Non-Payable Items", None),
        ("A1.1 Toiletries and Personal Care", "Toiletries, admission kits, soap, toothpaste and similar personal care items are not payable."),
        ("A1.2 Disposable Protective Items", "Disposable gloves, masks, aprons and caps are not payable."),
        ("A1.3 Disposables", "Syringes, needles, cotton and gauze are not payable."),
        ("A1.4 Nebulizer Kit", "Nebulizer kits are not payable."),
    ],
]

ENDORSEMENT_HEADER = [
    "Endorsement No. E-01 to Policy SYN-HP-2025-000123",
    "Insurer: Kalpavriksha Demo Insurance Co. (fictitious)",
    "Policy Number: SYN-HP-2025-000123",
    "Endorsement Issue Date: 15-Sep-2025",
    "Endorsement Effective Date: 01-Oct-2025",
    "Applies To: Hospitalisations commencing on or after 01-Oct-2025",
]

ENDORSEMENT_PAGES = [
    [
        ("Endorsement Provisions", None),
        ("E1.1 Revised Room Rent Limit", "This endorsement replaces clause 2.2. Room rent, boarding and nursing charges are payable up to INR 7,500 per day. Room charges above this limit are not payable. No proportionate deduction is applied to other expenses."),
        ("E1.2 Revised Co-payment", "This endorsement replaces clause 5.2. A co-payment of 5% applies to the admissible claim amount after the deductible."),
        ("E1.3 Consumables Cover", "Notwithstanding clause 4.1 and Annexure I, disposable gloves, masks and syringes used during hospitalisation are payable up to INR 5,000 per hospitalisation."),
    ],
]

BILL_HEADER = [
    "Synthetic Care Hospital (fictitious) - Itemised Final Bill",
    "Bill Number: SCH-SYN-88412",
    "Patient: Demo Policyholder A (synthetic)",
    "Policy Number: SYN-HP-2025-000123",
    "Bill Date: 15-Nov-2025",
    "Admission Date: 12-Nov-2025",
    "Discharge Date: 15-Nov-2025",
    "Diagnosis: Acute appendicitis",
    "Procedure: Laparoscopic appendicectomy",
]

# (description, service date, quantity, unit rate, amount) — all synthetic, illustrative values.
BILL_ITEMS = [
    ("Deluxe Room Charges", "12-11-2025", "2", "9,000.00", "18,000.00"),
    ("ICU Charges", "13-11-2025", "1", "12,000.00", "12,000.00"),
    ("Surgeon Fee - Lap. Appendicectomy", "13-11-2025", "1", "45,000.00", "45,000.00"),
    ("Anaesthetist Fee", "13-11-2025", "1", "12,000.00", "12,000.00"),
    ("OT Charges", "13-11-2025", "1", "18,000.00", "18,000.00"),
    ("CBC, LFT, RFT", "12-11-2025", "1", "3,200.00", "3,200.00"),
    ("USG Abdomen", "12-11-2025", "1", "2,500.00", "2,500.00"),
    ("Inj. Ceftriaxone 1g", "13-11-2025", "6", "400.00", "2,400.00"),
    ("MVI Infusion", "14-11-2025", "2", "900.00", "1,800.00"),
    ("Disposable gloves, masks & syringes", "13-11-2025", "1", "3,500.00", "3,500.00"),
    ("Admission kit & toiletries", "12-11-2025", "1", "1,200.00", "1,200.00"),
    ("Nebulizer kit", "14-11-2025", "1", "900.00", "900.00"),
    ("TV & telephone charges", "12-11-2025", "3", "200.00", "600.00"),
    ("Ambulance pickup", "12-11-2025", "1", "3,000.00", "3,000.00"),
    ("Dietitian consultation", "14-11-2025", "1", "800.00", "800.00"),
    ("Follow-up consultation", "25-11-2025", "1", "1,000.00", "1,000.00"),
]
BILL_TOTAL = "1,25,900.00"

# A SYNTHETIC "benefits at a glance" brochure. It deliberately misstates two terms (room rent and co-payment)
# and omits the consumables cap, so the Fraud & Fairness checks have a known discrepancy to find. Ambulance
# and deductible match the wording, so consistent terms can be shown as consistent.
BROCHURE_HEADER = [
    "Sahaay Secure Health Plan - Benefits at a Glance (Brochure)",
    "Insurer: Kalpavriksha Demo Insurance Co. (fictitious)",
    "Policy Number: SYN-HP-2025-000123",
    "Policy Period: 01-Apr-2025 to 31-Mar-2026",
    "Sum Insured: INR 5,00,000",
]
BROCHURE_PAGES = [
    [
        ("Key Benefits", None),
        ("S1.1 Room Rent", "Room rent, boarding and nursing charges are payable up to INR 10,000 per day."),
        ("S1.2 Co-payment", "A co-payment of 0% applies to the admissible claim amount."),
        ("S1.3 Road Ambulance", "Road ambulance charges are payable up to INR 2,000 per hospitalisation."),
        ("S1.4 Deductible", "An aggregate deductible of INR 10,000 applies per policy year to the total admissible claim amount."),
        ("S1.5 Consumables", "Disposable gloves, masks and syringes are payable."),
    ],
]

# An endorsement with no effective date: the ambiguous policy-version case.
UNDATED_HEADER = [
    "Endorsement No. E-02 to Policy SYN-HP-2025-000123",
    "Insurer: Kalpavriksha Demo Insurance Co. (fictitious)",
    "Policy Number: SYN-HP-2025-000123",
    "Endorsement Issue Date: 02-Nov-2025",
]
UNDATED_PAGES = [
    [
        ("Endorsement Provisions", None),
        ("E2.1 Revised ICU Limit", "This endorsement replaces clause 2.3. ICU charges are payable up to INR 15,000 per day."),
    ],
]
