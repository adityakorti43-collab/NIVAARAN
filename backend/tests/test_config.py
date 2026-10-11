"""Tests for app/config.py.

config.py reads environment variables ONCE, at import time, into module-level constants. To test different
environments safely we load it in a fresh Python subprocess each time; reloading the module inside the test
process could leak changed settings into every other test.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from app.config import BACKEND_DIR

# Everything we want to inspect, printed as JSON by the subprocess
_SNIPPET = (
    "import json, app.config as c;"
    "print(json.dumps({"
    "'MAX_UPLOAD_BYTES': c.MAX_UPLOAD_BYTES, 'MAX_PAGES': c.MAX_PAGES,"
    "'EMBEDDING_BACKEND': c.EMBEDDING_BACKEND, 'RERANKER_ENABLED': c.RERANKER_ENABLED,"
    "'CORS_ORIGINS': c.CORS_ORIGINS, 'DATA_DIR': str(c.DATA_DIR),"
    "'UPLOAD_DIR': str(c.UPLOAD_DIR), 'DB_PATH': str(c.DB_PATH)}))"
)


def load_config(**env) -> dict:
    """Import app.config in a clean subprocess with only the given NIVAARAN_* variables set."""
    clean = {k: v for k, v in os.environ.items() if not k.startswith("NIVAARAN_")}
    clean.update(env)
    out = subprocess.run([sys.executable, "-c", _SNIPPET], cwd=str(BACKEND_DIR), env=clean,
                         capture_output=True, text=True, check=True)
    # Logging goes to stderr, so the last stdout line is our JSON
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_defaults_when_no_env_vars_set():
    cfg = load_config()
    assert cfg["MAX_UPLOAD_BYTES"] == 15 * 1024 * 1024
    assert cfg["MAX_PAGES"] == 200
    assert cfg["EMBEDDING_BACKEND"] == "auto"
    assert cfg["RERANKER_ENABLED"] == "auto"
    assert cfg["CORS_ORIGINS"] == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_upload_and_page_limits_can_be_overridden():
    cfg = load_config(NIVAARAN_MAX_UPLOAD_MB="2", NIVAARAN_MAX_PAGES="5")
    assert cfg["MAX_UPLOAD_BYTES"] == 2 * 1024 * 1024
    assert cfg["MAX_PAGES"] == 5


def test_cors_origins_are_trimmed_and_blanks_dropped():
    cfg = load_config(NIVAARAN_CORS_ORIGINS=" http://a.example , ,http://b.example ")
    assert cfg["CORS_ORIGINS"] == ["http://a.example", "http://b.example"]


def test_data_dir_override_moves_uploads_and_database(tmp_path):
    cfg = load_config(NIVAARAN_DATA_DIR=str(tmp_path))
    assert Path(cfg["DATA_DIR"]) == tmp_path
    # Uploads and the SQLite file must live under the chosen data directory
    assert Path(cfg["UPLOAD_DIR"]) == tmp_path / "uploads"
    assert Path(cfg["DB_PATH"]) == tmp_path / "nivaaran.sqlite3"


def test_every_env_var_read_by_config_is_documented_in_env_example():
    # Guards against docs drift: a new NIVAARAN_* setting must be added to .env.example too
    source = (BACKEND_DIR / "app" / "config.py").read_text(encoding="utf-8")
    used = set(re.findall(r'"(NIVAARAN_[A-Z_]+)"', source))
    documented = (BACKEND_DIR.parent / ".env.example").read_text(encoding="utf-8")
    assert used, "expected config.py to read at least one NIVAARAN_* variable"
    missing = sorted(name for name in used if name not in documented)
    assert not missing, f"missing from .env.example: {missing}"
    