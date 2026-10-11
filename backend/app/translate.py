"""Site-wide translation into Indian languages, through Azure AI Translator (machine translation).

The page sends its visible English text in batches; this module translates it with Azure and keeps every translation in
the database, so each sentence is translated (and paid for) once. Numbers, rupee amounts and clause references pass
through unchanged.

Configure: NIVAARAN_AZURE_TRANSLATOR_KEY and NIVAARAN_AZURE_TRANSLATOR_REGION (e.g. centralindia). If they are not set,
the Speech key/region are tried, which works when both come from one multi-service "Azure AI services" resource.
Without a key, translation reports that it is off and the site stays in English; nothing is faked.
"""
from __future__ import annotations

import hashlib
import os
import re
import time
from collections import defaultdict

import httpx
from fastapi import HTTPException

from app import store
from app.config import log

KEY = os.environ.get("NIVAARAN_AZURE_TRANSLATOR_KEY") or os.environ.get("NIVAARAN_AZURE_SPEECH_KEY", "")
REGION = os.environ.get("NIVAARAN_AZURE_TRANSLATOR_REGION") or os.environ.get("NIVAARAN_AZURE_SPEECH_REGION", "")
ENDPOINT = "https://api.cognitive.microsofttranslator.com/translate"

# India's scheduled languages that Azure Translator supports (Sanskrit and Santali are not offered), plus Bhojpuri.
LANGUAGES = [
    ("en", "English", "English"), ("hi", "Hindi", "हिन्दी"), ("bn", "Bengali", "বাংলা"), ("te", "Telugu", "తెలుగు"),
    ("mr", "Marathi", "मराठी"), ("ta", "Tamil", "தமிழ்"), ("ur", "Urdu", "اردو"), ("gu", "Gujarati", "ગુજરાતી"),
    ("kn", "Kannada", "ಕನ್ನಡ"), ("ml", "Malayalam", "മലയാളം"), ("or", "Odia", "ଓଡ଼ିଆ"), ("pa", "Punjabi", "ਪੰਜਾਬੀ"),
    ("as", "Assamese", "অসমীয়া"), ("mai", "Maithili", "मैथिली"), ("ne", "Nepali", "नेपाली"), ("gom", "Konkani", "कोंकणी"),
    ("sd", "Sindhi", "سنڌي"), ("ks", "Kashmiri", "کٲشُر"), ("doi", "Dogri", "डोगरी"), ("mni", "Manipuri", "ꯃꯩꯇꯩꯂꯣꯟ"),
    ("brx", "Bodo", "बड़ो"), ("bho", "Bhojpuri", "भोजपुरी"),
]
CODES = {c for c, _, _ in LANGUAGES}
RTL = {"ur", "sd", "ks"}
MAX_TEXTS, MAX_CHARS = 120, 2000
_HOURLY = 6000                     # strings per client per hour that may go to Azure (cached ones are free)
_usage: dict[str, list[float]] = defaultdict(list)

_ready = False


def _ensure_table() -> None:
    global _ready
    if not _ready:
        store.execute("CREATE TABLE IF NOT EXISTS translations (lang TEXT NOT NULL, hash TEXT NOT NULL, text TEXT NOT NULL, PRIMARY KEY (lang, hash))")
        _ready = True


# Automated browser tests only: NIVAARAN_ENABLE_DEMO=1 + NIVAARAN_TRANSLATE_PROVIDER=test marks text as "⟦ta⟧ …" instead of
# calling Azure, so the page-translation mechanics can be tested without a key. Never active on a real server.
TEST = os.environ.get("NIVAARAN_TRANSLATE_PROVIDER") == "test" and os.environ.get("NIVAARAN_ENABLE_DEMO") == "1"


def _azure() -> bool:
    return bool(KEY and REGION)


def enabled() -> bool:
    from app import gemini
    return TEST or _azure() or gemini.enabled()


def languages() -> dict:
    return {"enabled": enabled(), "languages": [{"code": c, "name": n, "native": nat, "rtl": c in RTL} for c, n, nat in LANGUAGES],
            "provider": ("Azure AI Translator" if _azure() else "Google Gemini") + " (machine translation)" if enabled() else None}


# Amounts, percentages, dates and clause numbers are swapped for placeholders before machine translation and put back
# afterwards, so they can never be altered (e.g. a "₹" turned into "?"). If a placeholder goes missing, the English
# text is kept rather than risk a wrong number.
_PROTECT = re.compile(r"(?:₹|INR|Rs\.?)\s?\d[\d,]*(?:\.\d+)?|\d{1,2}[-/ ](?:\d{1,2}|[A-Z][a-z]{2})[-/ ]\d{2,4}|\b[A-Z]?\d+(?:\.\d+)+\b|\d[\d,]*(?:\.\d+)?%?")


def _protect(text: str) -> tuple[str, list[str]]:
    keep: list[str] = []

    def sub(m: re.Match) -> str:
        keep.append(m.group(0))
        return f"[[{len(keep) - 1}]]"
    return _PROTECT.sub(sub, text), keep


def _restore(translated: str, keep: list[str], original: str) -> str:
    out = translated
    for i, v in enumerate(keep):
        token = f"[[{i}]]"
        if token not in out:
            return original
        out = out.replace(token, v)
    return out


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def translate(texts: list[str], lang: str, client: str) -> list[str]:
    if lang not in CODES:
        raise HTTPException(status_code=422, detail="Unsupported language.")
    texts = [t[:MAX_CHARS] for t in texts[:MAX_TEXTS]]
    if lang == "en":
        return texts
    if not enabled():
        raise HTTPException(status_code=503, detail="Translation isn't set up on this server yet.")
    _ensure_table()
    out: list[str | None] = [None] * len(texts)
    hashes = [_h(t) for t in texts]
    if hashes:
        marks = ",".join("?" * len(hashes))
        cached = dict(store.query(f"SELECT hash, text FROM translations WHERE lang=? AND hash IN ({marks})", (lang, *hashes)))
        for i, h in enumerate(hashes):
            out[i] = cached.get(h)
    todo = sorted({i for i, v in enumerate(out) if v is None and texts[i].strip()}, key=lambda i: i)
    uniq: dict[str, list[int]] = defaultdict(list)
    for i in todo:
        uniq[texts[i]].append(i)
    if uniq:
        now = time.time()
        _usage[client] = [t for t in _usage[client] if now - t < 3600]
        if len(_usage[client]) + len(uniq) > _HOURLY:
            raise HTTPException(status_code=429, detail="Too many translations right now. Try again in a little while.")
        _usage[client] += [now] * len(uniq)
        src = list(uniq)
        if TEST:
            for t in src:
                for i in uniq[t]:
                    out[i] = f"⟦{lang}⟧ {t}"
            return [o if o is not None else texts[i] for i, o in enumerate(out)]
        if not _azure():   # Google Gemini (free tier)
            from app import gemini
            name = next(n for c, n, _ in LANGUAGES if c == lang)
            masked = [_protect(t) for t in src]
            results = []
            for i in range(0, len(masked), 20):   # small batches come back quickly on the free tier
                results += gemini.translate([m for m, _ in masked[i:i + 20]], name)
            results = [_restore(tr, keep, orig) for tr, (_, keep), orig in zip(results, masked, src)]
            for t, tr in zip(src, results):
                store.execute("INSERT OR REPLACE INTO translations (lang, hash, text) VALUES (?,?,?)", (lang, _h(t), tr))
                for i in uniq[t]:
                    out[i] = tr
            return [o if o is not None else texts[i] for i, o in enumerate(out)]
        try:
            r = httpx.post(ENDPOINT, params={"api-version": "3.0", "from": "en", "to": lang, "textType": "plain"},
                           headers={"Ocp-Apim-Subscription-Key": KEY, "Ocp-Apim-Subscription-Region": REGION, "Content-Type": "application/json"},
                           json=[{"Text": t} for t in src], timeout=30)
        except httpx.HTTPError as exc:
            log.warning("Azure translator request failed: %s", exc)
            raise HTTPException(status_code=502, detail="The translation service couldn't be reached. Try again.") from exc
        if r.status_code in (401, 403):
            raise HTTPException(status_code=503, detail="The translation service rejected this server's key. Check NIVAARAN_AZURE_TRANSLATOR_KEY and _REGION.")
        if r.status_code == 429:
            raise HTTPException(status_code=429, detail="The translation service is busy. Try again in a few seconds.")
        if r.status_code != 200:
            log.warning("Azure translator returned HTTP %s: %s", r.status_code, r.text[:200])
            raise HTTPException(status_code=502, detail="The translation service didn't answer. Try again.")
        results = [x["translations"][0]["text"] for x in r.json()]
        for t, tr in zip(src, results):
            store.execute("INSERT OR REPLACE INTO translations (lang, hash, text) VALUES (?,?,?)", (lang, _h(t), tr))
            for i in uniq[t]:
                out[i] = tr
    return [o if o is not None else texts[i] for i, o in enumerate(out)]
