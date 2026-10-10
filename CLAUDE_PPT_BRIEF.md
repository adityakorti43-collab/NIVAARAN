# Claude Brief: Create the Nivaaran Hackathon PPT

Use this brief together with the attached seven-page reference PDF/images. Create an editable PowerPoint presentation (`.pptx`) that follows the reference deck's structure and visual language while presenting the Nivaaran project accurately.

## Deliverable

- Save the presentation as `Nivaaran_FIN01.pptx`.
- Use 16:9 landscape slides, with exactly seven slides.
- Match the reference's white canvas, red organic corner shapes, red uppercase section headings, and restrained cyan/blue accents. Keep the supplied team/event logos in the header or cover if the attached assets are available.
- Use readable typography and comfortable text sizes. The reference's extracted serif text appears oversized; do not reproduce that legibility problem. Use a distinctive display face for headings and a clean sans-serif for body copy.
- Recreate diagrams and tables as editable PowerPoint elements where practical. Use genuine project screenshots only if provided; do not invent screenshots, logos, partners, metrics, or deployment claims.
- Keep each slide concise. Prefer diagrams, short labels, and compact bullet points over paragraphs.

## Project Facts: Treat These as Ground Truth

- Product name: **Nivaaran**
- Tagline: **Insurance clarity. Backed by evidence.**
- Challenge: **HackMatrix 5.0, FIN-01 — Policy-to-Patient: Insurance Coverage & Treatment Cost Intelligence**
- Team / affiliation: **Aishwaryam Nexus**
- Members:
  - Prem Munot — `124B1B264`
  - Aditya Korti — `S240105130`
  - Aayush Gabhane — `20240802545`
  - Arnav Sapkal — `25511562`
- The app is a decision-support prototype. It produces traceable estimates, not guaranteed insurer decisions or reimbursement amounts.
- Its demo policy, endorsement, sample claim, evaluation examples, and bundled treatment-cost table are synthetic/illustrative. Do not describe them as real patient, insurer, or hospital data.
- Users can upload their own policy wording, endorsements, benefit summaries, and itemized bills. Sensitive real records require permission, de-identification, and appropriate security controls.

## Accuracy Rules

- The implementation is a **React + TypeScript + Vite** frontend and a **FastAPI + Python** backend with SQLite storage. Do not call it a Streamlit app.
- Policy and bill documents are parsed using the project's ingestion/parsing pipeline; OCR is available when configured. Do not claim perfect OCR or universal document compatibility.
- Retrieval combines keyword BM25 and semantic retrieval, with evidence verification and clause/page references. Describe this as evidence-grounded retrieval, not as an unrestricted generative chatbot.
- Claim arithmetic is handled by a deterministic Decimal-based rules engine using policy terms such as deductibles, co-payments, limits, and exclusions. Unresolved evidence is flagged and estimates may be shown as a range.
- The assistant answers from retrieved documents and analysis. Optional external AI rewording is disabled by default; do not imply that an LLM is required for core calculations.
- Treatment-cost intelligence currently uses an explicitly illustrative synthetic cost table and/or user-entered amounts. Do not claim that a trained ML model, XGBoost, historical hospital dataset, or validated market prices are currently powering it.
- The app exposes extraction confidence, uncertainty, review states, missing information, and calculation invariants. Do not invent a calibrated overall probability that a claim will be approved.
- Do not claim that the app makes actual insurer adjudication decisions, detects fraud, or replaces a licensed professional. Fairness checks identify document/bill inconsistencies and are not fraud determinations.
- Do not claim FAISS, Streamlit, XGBoost, or a deployed hospital/insurer partnership; these appear in the reference concept but are not the current implementation.

## Website Inspection Instructions

Before writing slides, open **http://127.0.0.1:5173/** in a browser and inspect the page from top to bottom. Treat this website as the source of product language, visible examples, navigation names, and user-facing workflows. The attached PDF is only a visual-format reference. Do not use its project name, feature claims, or technical diagram as Nivaaran facts.

The landing page includes these product sections: hero and quick question prompt; premise; policy/endorsement/bill comparison; six bill-reading steps; exclusions and disagreements; a calculation trace; a cited assistant exchange; suggested next actions; “What's inside” feature list; and a security disclosure. Use the exact sample figures and synthetic labels described below where those sections are shown.

The application navigation is grouped as follows. If the demo can be opened, use **Try the demo** to inspect these screens; do not sign up with or invent real personal data:

- **Dashboard** (`/dashboard`): overview of the user's workspace and claims.
- **Analyse:** **Documents** (`/documents`) for policy/endorsement/benefit-summary upload and clause browsing; **Claim workspace** (`/claim`) for claim facts, bill editor, version, ledger, and calculation trace; **Evidence explorer** (`/evidence`) for clause search and evidence.
- **Understand:** **Claim map** (`/constellation`), **Money flow** (`/money-flow`), **What-if calculator** (`/what-if`), and **Assistant** (`/assistant`).
- **Act:** **Mismatch checks** (`/fairness`), **Next steps** (`/actions`), **Treatment costs** (`/costs`), **Evaluation** (`/evaluation`), and **Reports** (`/reports`). “ACT” is a navigation group, not one standalone feature. “Treatment costs” is not a live pricing page: its built-in ranges are illustrative, or the user can enter amounts.

If `127.0.0.1` is unreachable from your environment, do not pretend you inspected it. Use this brief as the verified page description and ask for screenshots only if a visual detail is necessary. Do not create fake product screenshots; use supplied captures or original labeled diagrams.

## Slide-by-Slide Content and Layout

Use the attached PDF as a **visual-format reference only**. Use the live Nivaaran landing page at `http://127.0.0.1:5173/` as the primary source for the story, terminology, and example. Keep its seven-slide count, but do **not** reuse the PDF's abstract wording, generic six-module descriptions, or 24-hour schedule. The deck should feel like a presentation of the website a reviewer can actually open.

### 1. Cover: Nivaaran

Follow the attached cover composition: event/team marks near the top, project identity centered, challenge details and team below. Use the exact team names and IDs from Project Facts. Feature the site's tagline: “Insurance clarity. Backed by evidence.” Do not use the reference project's name, PolicyCare AI.

### 2. The Bill Says One Number. The Insurer Pays Another.

Use the site's hero and Premise section as the content source. Center the real user problem: at discharge, the bill is reduced, but the patient cannot tell which policy clause explains each changed line. Nivaaran reads the policy and bill side by side, identifies what may be covered, excluded, or unresolved, and shows why with evidence.

Include the interface's real interaction cues: ask about a policy or claim; English, Hindi, and Marathi; exact clause references; “See a full claim breakdown.” State “No sign-up needed” only for the disposable synthetic demo. Make the estimate disclaimer visible: decision support only, not insurer approval or reimbursement.

### 3. One Treatment Date Changes Which Wording Applies

Recreate the landing page's three-source timeline as an explicitly **synthetic example**:

- **Policy wording · effective 01 Apr 2025:** room rent ₹5,000/day; consumables excluded; co-payment 10%.
- **Endorsement E-01 · effective 01 Oct 2025:** room rent becomes ₹7,500/day; consumables covered up to ₹5,000; co-payment becomes 5%.
- **Hospital bill · admission 12 Nov 2025:** date selects the post-endorsement version; show bill total ₹1,25,900 and representative lines such as deluxe room × 2 at ₹18,000 and gloves/masks at ₹3,500.

Show the relationship among the documents and admission date, rather than presenting these values as real contract terms. Add a conspicuous “Synthetic demo documents” caption.

### 4. From Upload to an Explainable Line Item

Use the site's “Reading the bill” six-step sequence, phrased in concise original copy and laid out as a flow:

1. Extract clauses with page number and exact wording.
2. Select the applicable policy version by effective date.
3. Itemize bill lines and check their arithmetic.
4. Apply limits in the order stated by the policy.
5. Match each charge to clauses whose terms actually apply.
6. Show disagreements between documents rather than silently choosing a side.

Add a small inspectable example: a vitamin infusion is conditional under clause 4.2 because the provided documents do not include the treating doctor's prescription. The estimate therefore does not count it as definitely payable; obtaining the prescription could resolve the missing evidence.

Use arrows, clause/page callouts, or a simple ledger motif. Do not repeat the reference PDF's proposed RAG/vector-database/LLM architecture as if it were the live pipeline.

### 5. Where the Synthetic Estimate Comes From

Build the main calculation waterfall from the landing page's exact synthetic sample. Preserve the arithmetic and show each subtraction:

- Original bill: **₹1,25,900** (16 items, as billed).
- Excluded or unresolved items held out: **−₹5,300** → ₹1,20,600.
- Item limits: **−₹6,000** → ₹1,14,600.
- Deductible: **−₹10,000** → ₹1,04,600.
- 5% co-payment: **−₹5,230** → **estimated payable ₹99,370**.

Label this “Synthetic demo claim · estimate, not insurer decision.” If adding the upper-bound estimate, derive it from the checked-in demo output and explain unresolved-item assumptions; otherwise omit it. Do not turn the sample into a performance result or real customer story.

### 6. Ask Why. See the Evidence. Choose a Next Step.

Use the website's “Questions,” “Exclusions & disagreements,” and “What's inside” sections to present actual interactive tools:

- **Assistant:** ask “Why didn't they pay for the vitamin drip?” and show the short answer: clause 4.2 makes vitamins conditional on a treating-doctor prescription; the supplied documents do not establish that prescription. It can reply in English, Hindi, or Marathi and cite the policy clause.
- **Mismatch checks:** place the fictional brochure's ₹10,000/day room statement beside the endorsement's ₹7,500/day limit; contrast with a clearly documented restriction, which is not automatically a discrepancy.
- **Next steps:** ask the insurer in writing, find the missing paper, check the relied-on clause, compare a cheaper-room what-if, or download a report.
- Briefly show the site's other tools by their real navigation names: Claim map, Money flow, What-if calculator, Evidence explorer, Reports, and Treatment costs.

Mark all quoted brochure/policy examples and the dialogue as synthetic. Do not label mismatch checks as fraud detection or imply that Nivaaran sends the drafted letter.

### 7. What Works Today—and What Needs Real-World Validation

Make a clear “implemented / next” close, then place team credits and compact references in the lower area:

- **Implemented:** private demo workspace, upload and parsing paths, effective-date versioning, item-level evidence, deterministic calculations, scenario analysis, mismatch findings, assistant citations, and reports.
- **Data boundary:** demo policy, endorsement, bill, brochure, evaluation set, and treatment-cost table are synthetic/illustrative; current cost ranges are not live prices. Real policy and bill uploads are supported by the product flow, but production use with identifiable records needs privacy/security review.
- **Security honesty:** the live site explicitly says there is no security certification/compliance attestation, files are not encrypted at rest, and deletion is standard deletion. It also describes hashed passwords, HTTP-only same-site sessions, per-account checks, local processing unless external AI is configured, and user-controlled deletion. Present both the protections and limitations; do not imply certification or encryption at rest.
- **Next validation:** test official insurer documents; obtain authorized, de-identified bill/outcome examples; source dated provider cost data; have independent reviewers check clause extraction and estimates.
- Credit Aishwaryam Nexus and list the supplied four members/IDs. Add a small methods/challenge reference block: BM25 (Robertson & Zaragoza, 2009), Sentence-BERT (Reimers & Gurevych, 2019), and the organizer-provided HackMatrix 5.0 FIN-01 statement. Do not invent a GitHub URL.

Close with: **“A traceable estimate is a starting point for a better question—not an insurer decision.”**

## Final Review Before Export

- Confirm there are exactly seven slides and that they follow the sequence above.
- Check that names and member IDs match the supplied list exactly.
- Check that synthetic/illustrative data is disclosed wherever demo results or cost estimates are shown.
- Remove unsupported accuracy, savings, adoption, approval-rate, cost-prediction, and partnership claims.
- Ensure all text fits, citations are readable, diagrams are editable, and the output opens as a PowerPoint file.