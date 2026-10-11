"""Google Gemini API (free tier available, key from Google AI Studio): natural speech and translation.

  NIVAARAN_GEMINI_API_KEY      the key from aistudio.google.com → Get API key (no card needed)
  NIVAARAN_GEMINI_TEXT_MODEL   default gemini-3.8-flash      (translation)
  NIVAARAN_GEMINI_TTS_MODEL    default gemini-3.8-flash-tts  (read-aloud)
  NIVAARAN_GEMINI_VOICE        default Kore (a clear female voice)

Uses the Interactions API (POST /v1beta/interactions). On Google's free tier, content sent may be used by Google to
improve its products; the paid tier does not do this.
"""
from __future__ import annotations

import base64
import io
import json
import os
import wave

import httpx
from fastapi import HTTPException

from app.config import log

KEY = os.environ.get("NIVAARAN_GEMINI_API_KEY", "")
TEXT_MODEL = os.environ.get("NIVAARAN_GEMINI_TEXT_MODEL", "gemini-3.8-flash")
TTS_MODEL = os.environ.get("NIVAARAN_GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
# Free-tier models get busy at peak times ("high demand"); when one is busy or out of quota, the next is tried.
TEXT_FALLBACKS = [TEXT_MODEL, "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
TTS_FALLBACKS = [TTS_MODEL, "gemini-3.8-flash-lite-tts", "gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts"]
VOICE = os.environ.get("NIVAARAN_GEMINI_VOICE", "Kore")
URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


def enabled() -> bool:
    return bool(KEY)


def _call_any(models: list[str], body: dict, timeout: float = 60) -> dict:  # noqa: D401
    """Try each model in turn while the previous one is busy (503), out of free quota (429) or not available (404)."""
    last: HTTPException | None = None
    for m in dict.fromkeys(models):
        try:
            return _call(body | {"model": m}, timeout)
        except HTTPException as exc:
            last = exc
            if exc.status_code not in (429, 502, 503) or "rejected this server's key" in str(exc.detail):
                raise
    raise last or HTTPException(status_code=502, detail="Google Gemini didn't answer. Try again.")


def _call(body: dict, timeout: float = 60) -> dict:
    try:
        r = httpx.post(URL, headers={"x-goog-api-key": KEY, "Content-Type": "application/json"}, json=body, timeout=timeout)
    except httpx.HTTPError as exc:
        log.warning("Gemini request failed: %s", exc)
        raise HTTPException(status_code=502, detail="Google Gemini couldn't be reached. Try again in a moment.") from exc
    if r.status_code in (401, 403):
        raise HTTPException(status_code=503, detail="Google Gemini rejected this server's key. Check NIVAARAN_GEMINI_API_KEY.")
    if r.status_code == 429:
        raise HTTPException(status_code=429, detail="The free Gemini quota is used up for now. Try again in a minute.")
    if r.status_code in (404, 503):
        log.info("Gemini model %s unavailable (HTTP %s), trying the next one", body.get("model"), r.status_code)
        raise HTTPException(status_code=503, detail="Google Gemini is busy right now. Try again in a minute.")
    if r.status_code != 200:
        log.warning("Gemini returned HTTP %s: %s", r.status_code, r.text[:300])
        raise HTTPException(status_code=502, detail="Google Gemini didn't answer properly. Try again.")
    return r.json()


def _outputs(resp: dict, kind: str) -> list[dict]:
    items = []
    for step in resp.get("steps", []) or []:
        if step.get("type") in ("model_output", None):
            items += [c for c in step.get("content", []) or [] if c.get("type") == kind]
    if not items:   # tolerate a flatter shape
        items = [c for c in resp.get("outputs", []) or [] if c.get("type") == kind]
    return items


def _wav(pcm: bytes, rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
    return buf.getvalue()


def speak(text: str) -> bytes:
    """WAV audio of `text` in a warm, clear female voice."""
    resp = _call_any(TTS_FALLBACKS, {
        "input": [{"type": "user_input", "content": [{"type": "text", "text": text, "annotations": [
            {"type": "speech_metadata", "style": "warm, clear and friendly, like a helpful Indian advisor explaining to a family; natural pace"}]}]}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": VOICE}]},
    }, timeout=90)
    audio = _outputs(resp, "audio")
    if not audio or not audio[-1].get("data"):
        raise HTTPException(status_code=502, detail="Google Gemini didn't return audio. Try again.")
    data = base64.b64decode(audio[-1]["data"])
    return data if data[:4] == b"RIFF" else _wav(data)   # raw 24 kHz 16-bit PCM gets a WAV header


def translate(texts: list[str], language: str) -> list[str]:
    """Translate short UI strings into `language`, keeping numbers, amounts and clause references exactly."""
    prompt = (
        f"Translate each string in this JSON array from English into {language}, for the interface of an Indian health-insurance "
        "help website used by ordinary families. Use simple, natural, everyday words a non-expert would understand, in the "
        "language's standard script. Keep these exactly as they are: numbers, rupee amounts (₹), percentages, dates, clause "
        "numbers such as 2.2 or A1.4, the name Nivaaran, and email addresses. Keep common insurance terms understandable "
        "(you may keep an English term in brackets when there is no common local word). Placeholders like [[0]] stand for numbers "
        "or amounts: copy every placeholder into the translation exactly once, unchanged. Return the translations in the same order.\n\n"
        + json.dumps(texts, ensure_ascii=False))
    resp = _call_any(TEXT_FALLBACKS, timeout=35, body={
        "input": prompt,
        "generation_config": {"thinking_level": "low", "temperature": 0.2},
        "response_format": {"type": "text", "mime_type": "application/json", "schema": {
            "type": "object", "properties": {"translations": {"type": "array", "items": {"type": "string"}}}, "required": ["translations"]}},
    })
    raw = "".join(c.get("text", "") for c in _outputs(resp, "text"))
    try:
        out = json.loads(raw)["translations"]
    except (ValueError, KeyError, TypeError) as exc:
        log.warning("Gemini translation was not valid JSON: %s", raw[:200])
        raise HTTPException(status_code=502, detail="The translation came back garbled. Try again.") from exc
    if len(out) != len(texts):
        log.warning("Gemini returned %d translations for %d strings", len(out), len(texts))
    return [str(out[i]) if i < len(out) and str(out[i]).strip() else t for i, t in enumerate(texts)]
