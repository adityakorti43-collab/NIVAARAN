# NIVAARAN backend

FastAPI service that ingests insurance policy PDFs, retrieves and verifies the relevant clauses, and runs a
deterministic `Decimal`-based rules engine to estimate what a hospital bill pays. For the full architecture,
design rules and demo walkthrough, see the [root README](../README.md).

## Requirements

- Python 3.11+ (developed on 3.11.9; the test suite also passes on Python 3.14.7, Windows)
- No API keys or secrets are needed to run it

## Setup

Run these from the `backend/` folder.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

- If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- `sentence-transformers` pulls in PyTorch, so the first install takes several minutes.
- The first semantic search downloads two small models from Hugging Face; after that it runs offline.

## Run the API

```powershell
uvicorn app.main:app --port 8000
```

- Health check: `GET http://localhost:8000/api/health`
- Interactive API docs: http://localhost:8000/docs
- To wipe all local data, stop the API and delete `data/runtime/`. It is recreated on the next start.

## Configuration

Every setting is an optional environment variable with a safe default. They are listed in
[`../.env.example`](../.env.example), which is a reference only and is not loaded automatically.
`app/config.py` reads them once at import time.

## Tests

```powershell
pytest -q
```

- Run it from `backend/`, because `pytest.ini` lives here (158 tests at the time of writing).
- Tests use a temporary data directory, so they never touch `data/runtime/`.

## Useful scripts

Run all of these from `backend/`.

- `python -m scripts.smoke` ingests the synthetic demo documents and prints the adjudication ledger.
  Use the `-m` form: `python scripts/smoke.py` fails with `No module named 'app'`.
- `python scripts/print_eval.py` prints a compact summary of `evaluation/results/latest.json`.
- `python -m app.evaluation.run_eval` re-runs the evaluation and rewrites `evaluation/results/`.
- `python -m demo.generate_demo` regenerates the synthetic demo PDFs in `demo/documents/`.

## Folder map

- `app/ingestion/`: upload validation, text extraction, clause segmentation
- `app/policy/`: clause interpretation and policy-version registry
- `app/bills/`: bill parsing and arithmetic checks
- `app/retrieval/`: BM25, semantic retrieval and reranking
- `app/verification/`: evidence verification and item decisions
- `app/engine/`: Decimal rules engine (deductible, co-pay, limits, caps)
- `app/adjudication/`: end-to-end claim adjudication and before/after comparison
- `app/costs/`: treatment-cost estimates on a labelled illustrative dataset
- `app/reports/`: PDF and JSON reports
- `app/qa/`: grounded assistant
- `tests/`, `evaluation/`, `demo/`, `scripts/`: tests, evaluation data and results, demo documents, helper scripts

## Contributing

- Keep financial calculations deterministic and testable: use `app/money.py`, never floats.
- Add or update tests when changing backend behavior, and run `pytest -q` before pushing.
- Never commit credentials, API keys or private user data.