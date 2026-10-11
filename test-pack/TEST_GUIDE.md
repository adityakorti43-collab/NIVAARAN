# Nivaaran test pack: Arogya Kavach (SYNTHETIC)

Everything here is fictitious and made up for testing: the insurer, hospital, patient, policy number and every amount.

The results below were produced by running these exact files through Nivaaran's API (`python -m demo.test_pack --verify`); nothing in the tables is typed by hand.

## Files

| File | Upload as | What it is |
|---|---|---|
| `1_policy_arogya_kavach.pdf` | Policy wording | 37 clauses: definitions, coverage, % of sum-insured and rupee limits, pre/post-hospitalisation windows, three waiting periods, exclusions (plain and conditional), deductible, co-payment, order of computation, claim requirements, precedence, Annexure II |
| `2_endorsement_A01_in_force.pdf` | Endorsement | A-01, effective 01-Feb-2026: replaces room rent (2.2) and co-payment (5.2); a 'Notwithstanding' clause overrides the consumables exclusion with a cap |
| `3_endorsement_A02_future_dated.pdf` | Endorsement | A-02, effective 01-Jun-2026 (after the treatment): raises the ICU limit. It must be ignored for this claim |
| `4_brochure_benefits_at_a_glance.pdf` | Benefits brochure | 'Benefits at a glance' with deliberate mismatches: room rent and deductible are misstated; physiotherapy omits its cap |
| `5_hospital_bill_angioplasty.pdf` | Hospital bill (on Claim workspace → New claim) | 22 lines, total ₹3,16,500.00; admitted 10-Mar-2026, discharged 14-Mar-2026 |

## How to test it on the website

1. **Documents** → upload the policy as *Policy wording*, both endorsements as *Endorsement / amendment*, and the brochure as *Benefits brochure*.
2. **Claim workspace → New claim** → choose the Arogya Kavach policy, tick both endorsements and the brochure, upload the bill, admission date **10-03-2026**, discharge **14-03-2026**, then analyse.
3. Compare what you see with the tables below. Then try the extras at the end (claim facts, What-if, Assistant, read-aloud).

## 1. Policy version chosen

- Selected: **Policy + A-01**
- Why: Treatment (admission) date 2026-03-10 falls within 'Policy + A-01' (2026-02-01 to 2026-05-31). Clause 2.2 replaced by E1.1 (A-01). Clause 5.2 replaced by E1.2 (A-01). Starts on endorsement effective date 2026-02-01 (endorsement states it applies to 'Hospitalisations commencing on or after 01-Feb-2026'). Later version(s) 'Policy + A-01 + A-02' from 2026-06-01 do not apply because they start after the treatment date.
- Designed outcome: A-01 applies (effective before admission); A-02 is ignored (effective after admission).

## 2. Line by line (first analysis: implant invoice and vitamin prescription not yet confirmed)

| # | Bill line | Billed | Designed to test | Nivaaran says | Eligible | Est. payable | Clauses |
|---|---|---|---|---|---|---|---|
| 1 | Private Room Charges | ₹14,000.00 | Room rent above the endorsed per-day limit (E1.1 replaces 2.2) | **Partly payable** | ₹10,000.00 | ₹8,272.23 | E1.1, 2.1 |
| 2 | ICU Charges | ₹20,000.00 | Per-day ICU limit (2.3); the future endorsement A-02 must NOT apply | **Partly payable** | ₹16,000.00 | ₹13,235.58 | 2.3 |
| 3 | Cath Lab Charges | ₹45,000.00 | Specific procedure coverage (2.10) | **Covered** | ₹45,000.00 | ₹37,225.07 | 2.10, 2.5 |
| 4 | Interventional Cardiologist Fee | ₹60,000.00 | Professional fees (2.4) | **Covered** | ₹60,000.00 | ₹49,633.42 | 2.4 |
| 5 | Anaesthetist Fee | ₹8,000.00 | Professional fees (2.4) | **Covered** | ₹8,000.00 | ₹6,617.79 | 2.4 |
| 6 | Drug Eluting Stent (implant) | ₹1,10,000.00 | Conditional coverage: needs the implant invoice (2.9) | **Conditional** | — | ₹0.00 | 2.9 |
| 7 | Coronary Angiography | ₹15,000.00 | Specific procedure coverage (2.10) | **Covered** | ₹15,000.00 | ₹12,408.35 | 2.10 |
| 8 | ECG and 2D Echo | ₹4,500.00 | Pre-hospitalisation, 18 days before admission: inside the 60-day window (2.7) | **Covered** | ₹4,500.00 | ₹3,722.51 | 2.7 |
| 9 | Cardiology Consultation | ₹1,500.00 | Pre-hospitalisation, 67 days before admission: outside the 60-day window (2.7) | **Excluded** | ₹0.00 | ₹0.00 | 2.7 |
| 10 | Blood tests - Lipid, Troponin, CBC | ₹5,200.00 | Diagnostic investigations (2.5) | **Covered** | ₹5,200.00 | ₹4,301.56 | 2.5 |
| 11 | Inj. Heparin and IV fluids | ₹9,800.00 | Medicines and drugs (2.6) | **Covered** | ₹9,800.00 | ₹8,106.80 | 2.6 |
| 12 | Multivitamin injection | ₹1,800.00 | Conditional exclusion: payable only if prescribed (4.2) | **Conditional** | — | ₹0.00 | 4.2, 2.6 |
| 13 | Disposable gloves, masks & syringes | ₹4,200.00 | Excluded (4.1) but overridden by 'Notwithstanding' E1.3, capped at INR 3,000 | **Partly payable** | ₹3,000.00 | ₹2,481.67 | E1.3 |
| 14 | ECG electrodes & cotton | ₹900.00 | Annexure exclusion (A2.3) with no override | **Excluded** | ₹0.00 | ₹0.00 | A2.3, 7.1 |
| 15 | Admission kit & toiletries | ₹1,500.00 | Exclusion (4.1 / A2.1) | **Excluded** | ₹0.00 | ₹0.00 | 4.1, A2.1 |
| 16 | Attendant food & guest meals | ₹1,800.00 | Comfort and guest exclusions (4.3 / A2.4) | **Excluded** | ₹0.00 | ₹0.00 | 4.3, A2.4 |
| 17 | Television charges | ₹1,000.00 | Comfort exclusion (4.3) | **Excluded** | ₹0.00 | ₹0.00 | 4.3 |
| 18 | Ambulance (home to hospital) | ₹3,500.00 | Per-hospitalisation ambulance limit (2.8) | **Partly payable** | ₹2,500.00 | ₹2,068.06 | 2.8 |
| 19 | Cardiac rehab physiotherapy | ₹6,000.00 | Post-hospitalisation (14 days after discharge) plus the physiotherapy cap (2.7, 2.11) | **Partly payable** | ₹5,000.00 | ₹4,136.12 | 2.11, 2.7 |
| 20 | Follow-up cardiology consultation | ₹1,500.00 | Post-hospitalisation, 47 days after discharge: inside the 90-day window (2.7) | **Covered** | ₹1,500.00 | ₹1,240.84 | 2.7 |
| 21 | Medical records & file charges | ₹500.00 | No clause mentions it: should stay unresolved, not guessed | **No evidence** | — | ₹0.00 | — |
| 22 | Dietitian consultation | ₹800.00 | No clause mentions it: should stay unresolved, not guessed | **No evidence** | — | ₹0.00 | — |

## 3. Claim-level checks

- **Initial Waiting Period**: satisfied. Coverage since 2023-01-01; admission 2026-03-10 is 1164 days later (waiting period 30 days).
- **Specific Disease Waiting Period**: not applicable. Diagnosis 'Coronary artery disease (single vessel)' is not among the listed conditions (treatment of cataract, hernia, kidney stones, joint replacement).
- **Pre-existing Diseases**: not applicable. Claim facts state the condition is not pre-existing (user-asserted).

## 4. The calculation

Order used: exclusion → item_limit → deductible → copay → sum_insured_cap (source: Policy clause 5.3 (Order of Computation)).

| | First analysis | After confirming implant invoice + vitamin prescription |
|---|---|---|
| Total billed | ₹3,16,500.00 | ₹3,16,500.00 |
| Eligible (definite) | ₹1,85,500.00 | ₹2,97,300.00 |
| Removed by exclusions and item limits | ₹17,900.00 | ₹17,900.00 |
| Deductible applied | ₹15,000.00 | ₹15,000.00 |
| Co-payment | ₹17,050.00 | ₹28,230.00 |
| **Estimated payable (definite)** | ₹1,53,450.00 | ₹2,00,000.00 |
| Payable if all unresolved items go your way | ₹2,00,000.00 | ₹2,00,000.00 |
| Your share (minimum) | ₹1,16,500.00 | ₹1,16,500.00 |
| Still unresolved | ₹46,550.00 | ₹0.00 |

First analysis, sum-insured cap step:  (₹1,53,450.00 → ₹1,53,450.00)

After confirmation, sum-insured cap step:  (₹2,54,070.00 → ₹2,00,000.00)

Lines that changed after confirming the facts:

- Line 6 Drug Eluting Stent (implant): Conditional → **Covered**, payable ₹0.00 → ₹73,999.33
- Line 12 Multivitamin injection: Conditional → **Covered**, payable ₹0.00 → ₹1,210.90

## 5. Mismatch checks (brochure vs policy)

Status: **Multiple issues require review**

- 3 issues together merit a written clarification (high severity)
- Room Rent: INR 8,000.00 in the summary vs INR 5,000.00 in the policy (high severity)
- Deductible differs between documents (high severity)
- Physiotherapy: the summary omits a cap (medium severity)
- Open-ended wording in clause 1.4 (low severity)
- Open-ended wording in clause 2.1 (low severity)
- Open-ended wording in clause A2.1 (low severity)

## 6. Read-aloud summaries

- English: What is covered (8), Limits on what is paid (3), What you pay yourself (2), Waiting periods (3), What is not covered (10)
- Hindi: क्या कवर है (8), भुगतान की सीमाएँ (3), आपको खुद क्या देना होगा (2), प्रतीक्षा अवधि (3), क्या कवर नहीं है (10)
- Marathi: काय कव्हर आहे (8), देय रकमेच्या मर्यादा (3), तुम्हाला स्वतः काय भरावे लागेल (2), प्रतीक्षा कालावधी (3), काय कव्हर नाही (10)

## 7. Questions to try in the Assistant

- **Why was the room charge reduced?** → grounded: Line 1 'Private Room Charges' (normalised: Private Room Charges) is partially payable. Payable under E1.1 (Revised Room Rent Limit), 2.1 (In-patient Hospitalisation Expenses). Item limit reduced the eligible amount by 4,000.00. Billed 14,000.00; eligible after…
- **Is the stent covered?** → grounded: Line 6 'Drug Eluting Stent (implant)' (normalised: Drug Eluting Stent (implant)) is potentially covered. 2.9 names this item more specifically (surgically implanted devices, stents) than 2.6 (drugs), so its condition governs. Payable under 2.9; the claim facts…
- **How much will I have to pay myself?** → grounded: Your estimated out-of-pocket share is 116,500.00 to 116,500.00 of the 316,500.00 billed. The insurer's estimated payable amount is 200,000.00 (definite) to 200,000.00 if every unresolved item is resolved favourably. The difference comes from excluded items, it…
- **क्या आईसीयू का पूरा खर्च मिलेगा?** → grounded: आपका सवाल इस तरह समझा गया: “is icu full payable”। नीचे का उत्तर आपके दस्तावेज़ों से है; हर राशि और धारा वहीं से ली गई है। Line 2 'ICU Charges' (normalised: icu intensive care unit Charges) is partially payable. Payable under 2.3 (Intensive Care Unit Charges). …
- **माझ्या खिशातून किती पैसे जातील?** → grounded: तुमचा प्रश्न असा समजला: “how much out of pocket”. खालील उत्तर तुमच्या कागदपत्रांवर आधारित आहे; प्रत्येक रक्कम आणि कलम तिथूनच घेतले आहे. Your estimated out-of-pocket share is 116,500.00 to 116,500.00 of the 316,500.00 billed. The insurer's estimated payable amo…

## 8. More things to try

- **Claim facts**: set *Implant invoice submitted* and *Vitamin prescription* to Yes and watch lines 6 and 12 change (section 4).
- **What-if calculator**: change the room to a ₹5,000 room, remove the TV line, or switch the version to 'base policy only' to see the 1%-of-sum-insured room limit apply.
- **Documents → Listen to this policy**: hear the summary in English, हिंदी or मराठी.
- **Next steps**: draft a clarification letter about the brochure mismatch.
- **Reports**: download the PDF and JSON evidence report.

