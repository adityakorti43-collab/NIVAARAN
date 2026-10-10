"""Runtime configuration. All values come from environment variables with safe defaults.

No secrets are required to run Nivaaran. Nothing here is sent to external services.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("NIVAARAN_DATA_DIR", BACKEND_DIR / "data" / "runtime"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "nivaaran.sqlite3"
DEMO_DIR = BACKEND_DIR / "demo"
EVAL_DIR = BACKEND_DIR / "evaluation"

MAX_UPLOAD_BYTES = int(os.environ.get("NIVAARAN_MAX_UPLOAD_MB", "15")) * 1024 * 1024
MAX_PAGES = int(os.environ.get("NIVAARAN_MAX_PAGES", "200"))

# Semantic retrieval. "auto" uses sentence-transformers when installed, else a labelled LSA fallback.
EMBEDDING_BACKEND = os.environ.get("NIVAARAN_EMBEDDINGS", "auto")  # auto | sentence-transformers | lsa
EMBEDDING_MODEL = os.environ.get("NIVAARAN_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
RERANKER_MODEL = os.environ.get("NIVAARAN_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANKER_ENABLED = os.environ.get("NIVAARAN_RERANKER", "auto")  # auto | off

CORS_ORIGINS = [o.strip() for o in os.environ.get(
    "NIVAARAN_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]


os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def ensure_dirs() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


logging.basicConfig(level=os.environ.get("NIVAARAN_LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for _noisy in ("httpx", "huggingface_hub", "sentence_transformers", "urllib3"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
# Document contents are never logged; only identifiers and counts.
log = logging.getLogger("nivaaran")
