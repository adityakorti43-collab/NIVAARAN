"""Load the operator's `.env` file (repository root) into the environment before any setting is read.

Real environment variables always win; the file only fills in what isn't already set. `.env` is gitignored, so
credentials put there stay on the server. Set NIVAARAN_NO_DOTENV=1 to skip it (the test suite does).
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def load(path: Path = ENV_FILE) -> list[str]:
    if os.environ.get("NIVAARAN_NO_DOTENV") == "1" or not path.is_file():
        return []
    loaded = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        key, value = key.strip(), value.split(" #", 1)[0].strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


LOADED = load()
