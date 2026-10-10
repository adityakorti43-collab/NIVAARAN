# Nivaaran

**Insurance clarity. Backed by evidence.**

Nivaaran is an AI-assisted health-insurance policy intelligence, treatment-cost analysis and itemised claim-adjudication
support platform (HackMatrix 5.0 problem **FIN-01 — Policy-to-Patient: Insurance Coverage & Treatment Cost Intelligence**).

Upload a policy wording, its endorsements and an itemised hospital bill. Nivaaran selects the policy version that applies on
the treatment date, matches every bill line to the clauses that govern it, verifies that evidence, and computes an itemised,
traceable estimate with a deterministic rules engine.

> Nivaaran produces **decision-support estimates only**. It never guarantees insurer approval, claim settlement or
> reimbursement. Every important financial conclusion is traceable to a clause excerpt and a reproducible calculation.

---

## Quick start (Windows PowerShell; macOS/Linux equivalents in brackets)

Prerequisites: Python 3.11+, Node.js 18+ (tested with Python 3.11.9 and Node 24.14.1).

```powershell
# 1. Backend
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu   # optional, smaller CPU build
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000            # [source .venv/bin/activate && uvicorn app.main:app --port 8000]

# 2. Frontend (second terminal)
cd frontend
npm install
npm run dev                                                                # http://localhost:5173
```

Open http://localhost:5173 and click **Try the demo**. Without an account this opens a private, disposable demo workspace
seeded with the synthetic case (deleted after 24 hours). No API keys or private credentials are needed.
The first semantic search downloads `all-MiniLM-L6-v2` (~90 MB) and the reranker (~90 MB) from Hugging Face once; after that
everything runs offline.

### Running the demo

1. **Landing → Try the demo** (or, when signed in, **Dashboard → Add the synthetic demo case**). This runs the real
   pipeline: the synthetic policy PDF and bill PDF are ingested first, then endorsement E-01 is added, which records a
   before/after comparison. Every visitor gets an isolated copy, so the demo is repeatable and never shared.
2. **Claim workspace** — expand ledger rows to see exact clause excerpts, pages, verification outcomes and per-item calculations.
   Scroll to *Before and after* to see why the estimate rose from ₹86,490 to ₹99,370 when E-01 was added.
3. Change **Claim facts** (e.g. *vitamin prescribed → yes*) and save: the MVI infusion moves from *conditional* to *covered*,
   and the change is recorded with its cause.
4. **What-If lab** — set the treatment date to 2025-09-20 (before E-01) or co-payment to 0 % and recalculate.
5. **Hospital bill lines** (claim workspace) — *Correct lines*, change an amount and save: the line is marked
   *Corrected by you*, the originally extracted value is kept beside it, totals and the stated-total check are recomputed on
   the server, and the claim is re-analysed. *Confirm lines are correct* records your review.
6. **Claim Clarity Map**, **Money flow**, **Evidence explorer**, **Nivaaran AI** (conversation is saved per claim),
   **Fraud & Fairness**, **Action Center**, **Cost intelligence**, **Evaluation** (click *Run evaluation*),
   **Reports** (PDF/JSON download; each generated report is listed on the dashboard).
7. Sign out and back in, or reload: claims, analyses, scenarios, chats and reports are read back from the database.

### Website navigation

The workspace groups its tools by task:

| Group | Pages | What they do |
|---|---|---|
| **Overview** | Dashboard | Overview of the signed-in workspace, claims, and recent activity. |
| **Analyse** | Documents · Claim workspace · Evidence explorer | Upload policies, endorsements and benefit summaries; review a bill and its extracted lines; inspect the applicable version, itemized estimate, and supporting clauses. |
| **Understand** | Claim map · Money flow · What-if calculator · Assistant | Explore links between charges and clauses, see how amounts change through the calculation, compare hypothetical changes, and ask evidence-grounded questions. |
| **Act** | Mismatch checks · Next steps · Treatment costs · Evaluation · Reports | Review document inconsistencies, prepare questions for an insurer, explore explicitly illustrative treatment-cost ranges or enter amounts, run the synthetic evaluation, and download reports. |

**Treatment costs is not live pricing.** Its built-in procedure ranges are authored illustrative data, not surveyed hospital prices. User-entered costs can be analyzed separately. The evaluation page also uses a small synthetic dataset and is not evidence of performance on real claims.

**Demo reset:** the demo is seeded per visitor from `backend/demo/documents/` through the normal pipeline, so there is
nothing shared to reset. To regenerate the synthetic PDFs run `python -m demo.generate_demo` from `backend/`. To wipe all
local data (all accounts), stop the API and delete `backend/data/runtime/`; it is recreated on the next start.

---

## Accounts, data and AI configuration

- **Accounts:** register, sign in, sign out, profile, change password, delete account, password reset (single-use tokens,
  30-minute expiry). Passwords use salted scrypt hashes, with an explicitly labelled PBKDF2-HMAC-SHA256 fallback on platforms
  where scrypt is unavailable. Sessions are 256-bit random tokens in an HttpOnly,
  SameSite=Lax cookie, stored server-side and expiring after `NIVAARAN_SESSION_DAYS` (default 7). Failed logins are rate-limited.
- **Sign in with Google, Apple or a phone number** (in addition to email and password). Google and Apple use the server-side
  OAuth authorization-code flow with a single-use, hashed `state`; the ID token is read from the provider's token endpoint and its
  issuer, audience and expiry are checked. An existing account with the same verified email is linked rather than duplicated.
  Each provider switches on only when configured; until then the buttons are shown disabled with an explanation.
  - Google: `NIVAARAN_GOOGLE_CLIENT_ID`, `NIVAARAN_GOOGLE_CLIENT_SECRET`.
  - Apple: `NIVAARAN_APPLE_CLIENT_ID` (Services ID) and `NIVAARAN_APPLE_CLIENT_SECRET` (the ES256 client-secret JWT generated
    with your Apple key; Apple allows up to six months' validity, so regenerate it before it expires).
  - Register these redirect URIs with the provider: `{NIVAARAN_PUBLIC_URL}/api/auth/google/callback` and
    `{NIVAARAN_PUBLIC_URL}/api/auth/apple/callback` (`NIVAARAN_PUBLIC_URL` defaults to `http://localhost:5173`).
  - Phone: a 6-digit code, stored only as a keyed hash, valid for 10 minutes, at most 5 attempts, and at most one code per
    30 seconds and five per hour for a number. Text messages are sent through Twilio when `NIVAARAN_TWILIO_ACCOUNT_SID`,
    `NIVAARAN_TWILIO_AUTH_TOKEN` and `NIVAARAN_TWILIO_FROM` are set; otherwise the code goes to the server outbox. For local
    testing only, `NIVAARAN_DEV_OTP=1` also shows the code on screen (set in `.claude/launch.json` and the Playwright test
    server); never set it on a public server. Set `NIVAARAN_OTP_PEPPER` so codes survive a server restart.
  - Accounts created this way have no password; they can add one in Settings.
- **Email is not connected.** Password-reset links are written to `backend/data/runtime/outbox/` on the server instead of
  being emailed. Connecting an SMTP or email API provider is remaining setup for a real deployment.
- **Database:** SQLite (`backend/data/runtime/nivaaran.sqlite3`) with versioned migrations (`PRAGMA user_version`). Domain
  records are stored as Pydantic-validated JSON beside indexed owner and claim columns; sessions and reset tokens have foreign
  keys that cascade on account deletion (domain tables are cleaned up by the application, not by FK constraints). It stores
  users, sessions, documents and their extracted clauses, claims and bills (including user corrections), every analysis run,
  before/after comparisons, saved What-If scenarios, assistant conversations and generated-report records. Created
  automatically on first start; no setup step is required.
- **Isolation:** every data endpoint resolves the user from the session on the server and checks ownership; records owned by
  another account return 404 (tested for claims, documents, page images, downloads, reports, chats and scenarios).
- **Read-aloud in English, Hindi and Marathi:** on Documents, "Listen to this policy" plays a plain-language summary of the
  whole policy (what is covered, limits, what you pay yourself, waiting periods, what is not covered) in any of the three
  languages, or reads the full wording clause by clause. Single clauses and assistant answers can be heard in all three too.
  Summaries are built deterministically from each clause's structured reading and cite their clauses; speech uses the
  browser's built-in voices (Marathi falls back to a Hindi voice when no Marathi voice is installed).
- **Questions in Hindi or Marathi:** the assistant maps common insurance and hospital terms to English for retrieval, answers
  from the documents as usual, and opens its reply with a line in the asker's language showing how the question was read.
- **Optional live AI:** off by default. With `NIVAARAN_AI_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` set, Claude
  (`NIVAARAN_AI_MODEL`, default `claude-opus-5-5`) may reword answers that were already assembled from cited clauses and engine
  results; a rewording that introduces any new number is discarded. Each answer states which engine produced it. Without a key,
  the assistant is the deterministic, evidence-grounded engine and says so — it is never presented as a live AI service.
- All variables are listed in `.env.example`.

---

## What the demo demonstrates (all synthetic, generated through the pipeline)

`backend/demo/` contains a fictitious policy (*Kalpavriksha Demo Insurance Co.*), endorsement E-01 and a 16-line bill
(*Synthetic Care Hospital*). Every page carries a "SYNTHETIC DEMONSTRATION DOCUMENT" banner. Regenerate with
`python -m demo.generate_demo` from `backend/`.

| Bill item | Outcome (with E-01) | Why |
|---|---|---|
| Deluxe room ₹9,000 × 2 days | Partially payable ₹15,000 | E1.1 replaces 2.2: ₹7,500/day (was ₹5,000) |
| ICU ₹12,000 | Partially payable ₹10,000 | 2.3 ICU limit |
| Surgeon, anaesthetist, OT, labs, USG, medicines | Potentially covered | 2.1, 2.4, 2.5, 2.6 |
| MVI infusion | **Conditional** | 4.2 excludes vitamins *unless prescribed* — prescription not established |
| Gloves, masks & syringes | Covered (was **excluded**) | E1.3 "Notwithstanding 4.1 and Annexure I" overrides the exclusion, ₹5,000 shared limit |
| Admission kit, TV/telephone | Potentially excluded | 4.1/A1.1, 4.3 |
| Nebulizer kit | **Conflicting evidence** | 2.10 says payable; Annexure A1.4 says not payable; precedence clause 7.1 doesn't resolve two specific clauses |
| Ambulance ₹3,000 | Partially payable ₹2,000 | 2.8 per-hospitalisation limit |
| Dietitian consultation | **Insufficient evidence** | No clause addresses it — not assumed covered or excluded |
| Follow-up consultation (10 days after discharge) | Potentially covered | 2.7 post-hospitalisation window (60 days) |

Hand-checked totals (also asserted in `tests/test_engine.py`):

| Version | Eligible (definite) | Deductible | Co-pay | Estimated payable |
|---|---|---|---|---|
| Base policy (treatment before 1 Oct 2025) | ₹1,06,100 | ₹10,000 | 10 % | **₹86,490** – ₹89,640 |
| Policy + E-01 (treatment 12 Nov 2025) | ₹1,14,600 | ₹10,000 | 5 % | **₹99,370** – ₹1,02,695 |

The lower figure is the definite estimate; the upper figure applies only if every unresolved item were resolved favourably.

---

## Insurance Truth Engine features (added)

All features read the same analysis (documents → applicable version → evidence → ledger → engine), so they never disagree.

- **Fraud & Fairness Intelligence** (`/fairness`, `GET /api/claims/{id}/fairness`, `app/fairness/scan.py`): deterministic cross-document
  checks — benefit summary vs issued wording (limits, co-payment, deductible, exclusions, omitted caps), contradictory clauses, amendment-date
  problems, bill arithmetic, engine reconciliation, clause-numbering gaps, open-ended wording. Severity and evidence completeness are separate;
  documented exclusions are listed as *restrictive but documented*, never as discrepancies. No fraud classifier, no probability scores.
  The demo includes a synthetic brochure that misstates room rent (₹10,000 vs ₹7,500) and co-payment (0% vs 5%) and omits the consumables cap.
- **Consumer Action Center** (`/actions`, `GET /api/claims/{id}/actions`): questions for the insurer tied to ledger items and findings,
  missing documents, unresolved amounts, and an editable, neutral clarification letter (no accusations, no legal deadlines; never sent).
- **Nivaaran AI copilot** (launcher on every workspace page): `POST /api/claims/{id}/ask` now accepts `context` (selected bill item, finding,
  current view). New intents: coverage summary, discrepancies / "was I misled", draft a clarification request, what to ask, plain-language
  explanations. Answers return citations and real action buttons (open clause source, open ledger item, open page). Template-based over
  retrieved clauses and engine output — no LLM, so nothing is invented.
- **Claim Clarity Map** (`/constellation`) and **Out-of-Pocket Simulator** (`/what-if`) are the renamed constellation and What-If Lab.
- **Cinematic introduction**: real-time three.js scene (scanning ring over a holographic policy, evidence nodes), once per session,
  skippable, skipped under reduced motion, text-only without WebGL. Add `?nointro` to the URL to bypass it.
- Upload a brochure with document type `benefit_summary`. `synthetic_endorsement_E02_undated.pdf` demonstrates the ambiguous-version case.

## Architecture

```
frontend/  React 19 + TypeScript + Vite + Tailwind CSS v4, React Flow, Recharts, Motion
backend/   FastAPI + Pydantic, PyMuPDF, scikit-learn, sentence-transformers, SQLite (stdlib)
  app/ingestion/      upload validation (magic bytes, size, page limits), text extraction, OCR detection, clause segmentation
  app/policy/         deterministic clause interpretation; policy-version registry (effective dates, replacements, conflicts)
  app/bills/          PDF-table / CSV / JSON bill parsing, line & total arithmetic checks (amounts never altered)
  app/retrieval/      normalisation lexicon, Okapi BM25 baseline, semantic retrieval, RRF fusion, cross-encoder reranker
  app/verification/   evidence verification (support / exclusion / condition / override / irrelevant) and item decisions
  app/engine/         Decimal rules engine: policy-stated stage order, unique adjustment IDs, shared-limit pools, invariants
  app/adjudication/   end-to-end adjudication, ledger, before/after comparison
  app/qa/             grounded assistant (template answers over retrieved clauses + engine output; no LLM)
  app/costs/          treatment-cost intelligence over a labelled illustrative dataset or user-entered amounts
  app/reports/        PDF (PyMuPDF Story) and JSON reports
  app/evaluation/     reproducible retrieval/verification evaluation
```

**Pipeline per bill item:** normalise description (abbreviations, category) → retrieve candidates from clauses active in the
applicable version (union of BM25 top-8 and semantic top-8) → **verify** each candidate: a clause counts only if one of its
own scope terms matches the item, directly or via the item's category → decide using only precedence rules found in the
documents (endorsement "notwithstanding" overrides; the policy's specific-exclusion precedence clause) → otherwise report
conflict/insufficient evidence → deterministic engine.

**Key design rules**

- Similarity scores are *retrieval relevance only*; they are displayed separately from evidence support, extraction
  confidence and calculation certainty, and never combined into a "coverage probability".
- Financial maths never touches a model: `Decimal`, ROUND_HALF_UP to paise, largest-remainder allocation so items reconcile
  to claim totals. Stage order comes from the policy's computation-order clause (5.3); if absent, a default is used and
  flagged as *assumed*.
- Double-deduction prevention: each adjustment has an ID `scenario:stage:item:clause`; registering one twice raises.
  Deductible and co-payment are computed once on the claim total and allocated, never applied per item.
- Invariants checked on every analysis (shown in the UI): non-negative amounts, payable ≤ eligible ≤ claimed, totals
  reconcile, no duplicate adjustments, shared limits within pool, deductible within remaining amount, unresolved items never
  payable in the definite estimate, rounding to paise.
- Version selection uses effective dates and the documents' applicability statements — never upload order or upload date.
  Missing dates, policy-number mismatches, out-of-period dates, overlapping replacements and unclear retrospectivity are
  reported as conflicts requiring review.
- What-If scenarios and cost estimates run through the same `adjudicate()` function and are labelled HYPOTHETICAL.

### API (selected)

`GET /api/health` · `POST /api/documents` (policy/endorsement) · `GET /api/documents[/{id}[/clauses]]` ·
`GET /api/policies/{id}/versions` · `POST /api/bills/parse` · `POST /api/claims` · `PATCH /api/claims/{id}` ·
`POST /api/claims/{id}/scenario` · `POST /api/claims/{id}/compare-versions` · `POST /api/claims/{id}/ask` ·
`GET /api/claims/{id}/evidence?q=` · `GET /api/claims/{id}/report.pdf|json` · `GET /api/costs` · `POST /api/costs/estimate` ·
`POST /api/evaluation/run` · `GET /api/evaluation/results` · `POST /api/demo/load` · `DELETE /api/data?confirm=true`.
Interactive docs at http://localhost:8000/docs.

---

## Evaluation

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.evaluation.run_eval     # writes evaluation/results/latest.json and latest.md
```

60 labelled synthetic queries (`backend/evaluation/labeled_queries.json`) over the demo policy + E-01: direct keywords,
paraphrases, abbreviations, synonyms/spelling variants, exclusions, conditional coverage, conflicts, missing evidence,
amendment overrides, similar-but-inapplicable clauses and rule-lookup queries. Group-level split (paraphrases never straddle
splits), seed 42: 23 dev / 37 eval queries.

Measured on the held-out eval split (33 queries with relevant clauses; run on 2026-10-10):

| Method | Recall@1 | Recall@3 | MRR | nDCG@5 |
|---|---|---|---|---|
| BM25 · raw bill text | 0.657 | 0.838 | 0.826 | 0.822 |
| Semantic (all-MiniLM-L6-v2) · raw | 0.763 | 0.889 | 0.934 | 0.901 |
| BM25 · normalised | 0.798 | 0.980 | 0.970 | 0.970 |
| Semantic · normalised | 0.808 | 0.950 | 0.985 | 0.965 |
| Hybrid (RRF) · normalised | 0.838 | 0.975 | 1.000 | 0.990 |
| Hybrid + cross-encoder rerank · normalised | 0.838 | 1.000 | 1.000 | 1.000 |

On raw bill wording, semantic retrieval beats the keyword baseline (MRR 0.934 vs 0.826); the normalisation lexicon closes most
of the gap for BM25. Evidence verification on the 32 labelled eval items: accuracy 1.000, unsupported-answer rate 0.0 (dev
split: 21 items, accuracy 1.000 after one fix — see below).

**Read these numbers with care:** the dataset is small and synthetic, and the queries, labels and lexicon were written by the
same team, so results are optimistic and do not generalise to real policies. One dev-split error ("Blood bank processing
charges" wrongly verified as covered under diagnostics) was found and fixed during development by narrowing the lexicon.
Full per-query results, error examples and metric definitions are in the Evaluation workspace and `latest.json`.

---

## Tests

```powershell
cd backend;  .\.venv\Scripts\python.exe -m pytest -q          # 129 tests
cd frontend; npx playwright test                              # 60 browser tests (uses installed Chrome; starts servers if needed)
```

Backend tests cover PDF extraction, unsupported/corrupted/empty/scanned files, clause metadata, policy-version edge cases
(before/after amendment, missing/conflicting/out-of-period dates, overlapping and chained endorsements, unclear
retrospectivity), retrieval and verification (keywords, paraphrases, synonyms, exclusions, irrelevant clauses, missing and
conflicting evidence, time windows), the financial engine (limits, shared limits, deductible, co-pay, rule order, duplicate
deduction, rounding, sum-insured cap, waiting periods, before/after results), accounts and sessions, password reset,
user-to-user isolation, bill corrections (provenance, preserved originals, server-recomputed totals) and the full HTTP
workflow. Browser tests cover registration and validation, sign-out/sign-in persistence, protected-route redirects,
cross-account 404s, the demo entry, navigation, ledger evidence, version selection, comparison, What-If (saved scenarios
leave the saved analysis unchanged), assistant and saved chat history, copilot, constellation, real PDF/JSON downloads, bill
correction, upload errors, the intro (skip, remembered, reduced motion), landing sections and mobile layouts. A launch gate
(`e2e/console.spec.ts`) opens all 18 pages and fails on any console error, uncaught exception or 5xx API response.

## Running in VS Code

1. **File → Open Workspace from File…** and pick `nivaaran.code-workspace`. Accept the recommended extensions
   (Python, Python Debugger, Playwright, Tailwind CSS).
2. First time only: **Terminal → Run Task… → Setup: everything** (creates `backend/.venv`, installs Python and npm packages).
3. **Run and Debug** (Ctrl+Shift+D) → **Nivaaran: full stack** → F5. This starts the API with the debugger attached
   (breakpoints work in `backend/app`), starts the Vite dev server and opens Chrome at http://localhost:5173.
4. Tests: **Run Task… → Test: backend (pytest)** or **Test: browser (Playwright)**; pytest also appears in the Testing panel.

The workspace runs the API with `NIVAARAN_DEV_OTP=1` so phone sign-in codes appear on screen locally. Don't use it on a public server.

## Production build (single process)

```powershell
cd frontend; npm run build                                   # writes frontend/dist
cd ..ackend
$env:NIVAARAN_COOKIE_SECURE = "1"                            # behind HTTPS
$env:NIVAARAN_DATA_DIR = "D:
ivaaran-data"                 # persistent storage for the database and uploads
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

When `frontend/dist` exists, the API also serves the web app from the same origin (client-side routes fall back to
`index.html`; `/api/*` is never shadowed), so no separate web server or CORS setup is needed. Every response carries
`X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy` and `Permissions-Policy`; API responses are `no-store`.
Put it behind an HTTPS reverse proxy. See "Before a production deployment" below for what is still outstanding.

---

## Security & privacy

- Uploads are validated by content signature, size (15 MB) and page count; PDFs are parsed for text only, never executed.
- Stored files use random IDs; user filenames are sanitised; internal paths are never returned by the API.
- Document text is never logged. No document is sent to an external service unless the operator enables the optional
  Claude rewording, in which case the question, the cited excerpts and the deterministic answer are sent to the Anthropic API.
- Passwords hashed (scrypt, or PBKDF2-HMAC-SHA256 fallback when unavailable); HttpOnly session cookies; server-side authorisation on every data endpoint; secrets only via
  environment variables, never sent to the browser.

**Before a production deployment (not done):** HTTPS with `NIVAARAN_COOKIE_SECURE=1`; CSRF tokens for state-changing requests
(currently mitigated only by SameSite=Lax and JSON content types); a real email provider for password reset; encryption at
rest and backups for the database and uploads; a managed database instead of local SQLite for multi-instance hosting; malware
scanning of uploads; audit logging and retention policies; an independent security review. No certification or regulatory
compliance is claimed.
- Deleting a document removes its record and stored bytes (ordinary file deletion — not a secure wipe; files are not
  encrypted at rest). Documents in use by a claim cannot be deleted until the claim is deleted.

## Known limitations

- Clause interpretation is deterministic and pattern-based, tuned to clearly drafted, numbered wordings. Unusual phrasing
  falls back to "not interpreted" (treated as no evidence), which is safe but may produce more *insufficient evidence* results.
- OCR requires Tesseract on the server (not installed in this setup); scanned PDFs are rejected with an explicit message.
- A bill line combining items with different treatment (e.g. "syringes and needles" after E-01) is decided as one item.
- Room/ICU quantities are taken as days; a per-eye limit uses quantity as eye count.
- The cost-intelligence table is illustrative synthetic data, not market prices.
- Without the optional Claude configuration, the assistant is template-based over retrieved evidence, so it handles a
  defined set of question types.
- Bill corrections apply to line items; bill-level metadata (hospital, dates) is edited through the claim's dates instead.
- The first demo entry after a cold start waits for the retrieval models to load; the API now pre-loads them in the
  background at startup.
