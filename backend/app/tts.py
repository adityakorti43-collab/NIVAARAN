"""Natural-sounding speech for the read-aloud, through Azure AI Speech (neural voices).

Browsers only offer the voices installed on the device, and most Windows PCs have no Hindi voice at all. With Azure
configured, the same smooth neural voices speak both languages on every device:
  English: en-IN-NeerjaNeural   Hindi: hi-IN-SwaraNeural   (override with NIVAARAN_TTS_VOICE_EN / _HI)
Configure: NIVAARAN_AZURE_SPEECH_KEY and NIVAARAN_AZURE_SPEECH_REGION (e.g. centralindia). Without them this module
reports that it is off and the page falls back to the browser's own voices; nothing is faked.

Privacy: when enabled, the text being read (a policy summary or an assistant answer) is sent to Azure to be spoken.
Generated audio is cached on this server by a hash of (voice, text), so replaying is instant and costs nothing.
"""
from __future__ import annotations

import hashlib
import os
from html import escape

import httpx
from fastapi import HTTPException

from app.config import DATA_DIR, log

KEY = os.environ.get("NIVAARAN_AZURE_SPEECH_KEY", "")
REGION = os.environ.get("NIVAARAN_AZURE_SPEECH_REGION", "")
VOICES = {"en": os.environ.get("NIVAARAN_TTS_VOICE_EN", "en-IN-NeerjaNeural"),
          "hi": os.environ.get("NIVAARAN_TTS_VOICE_HI", "hi-IN-SwaraNeural")}
LOCALES = {"en": "en-IN", "hi": "hi-IN"}
CACHE = DATA_DIR / "tts-cache"
MAX_CHARS = 5000


def _azure() -> bool:
    return bool(KEY and REGION)


def enabled() -> bool:
    from app import gemini
    return _azure() or gemini.enabled()


def provider() -> str | None:
    from app import gemini
    return "azure" if _azure() else "gemini" if gemini.enabled() else None


def _ssml(text: str, lang: str) -> str:
    # A touch faster than default and a gentle, conversational style; the page adjusts speed further on playback.
    return (f"<speak version='1.0' xml:lang='{LOCALES[lang]}' xmlns='http://www.w3.org/2001/10/synthesis'>"
            f"<voice name='{VOICES[lang]}'><prosody rate='+8%'>{escape(text)}</prosody></voice></speak>")


def synthesize(text: str, lang: str) -> bytes:
    if not enabled():
        raise HTTPException(status_code=503, detail="The natural voice isn't set up on this server.")
    if lang not in VOICES:
        raise HTTPException(status_code=422, detail="Unsupported language.")
    text = " ".join(text.split())[:MAX_CHARS]
    if not text:
        raise HTTPException(status_code=422, detail="Nothing to read.")
    if not _azure():   # Google Gemini (free tier): same cache, WAV audio
        from app import gemini
        key = hashlib.sha256(f"gemini|{gemini.TTS_MODEL}|{gemini.VOICE}|{text}".encode()).hexdigest()
        path = CACHE / f"{key}.wav"
        if path.exists():
            return path.read_bytes()
        audio = gemini.speak(text)
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audio)
        return audio
    key = hashlib.sha256(f"{VOICES[lang]}|{text}".encode()).hexdigest()
    path = CACHE / f"{key}.mp3"
    if path.exists():
        return path.read_bytes()
    try:
        r = httpx.post(f"https://{REGION}.tts.speech.microsoft.com/cognitiveservices/v1", content=_ssml(text, lang).encode("utf-8"),
                       headers={"Ocp-Apim-Subscription-Key": KEY, "Content-Type": "application/ssml+xml",
                                "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3", "User-Agent": "nivaaran"}, timeout=30)
    except httpx.HTTPError as exc:
        log.warning("Azure speech request failed: %s", exc)
        raise HTTPException(status_code=502, detail="The voice service couldn't be reached. Try again in a moment.") from exc
    if r.status_code in (401, 403):
        raise HTTPException(status_code=503, detail="The voice service rejected this server's key. Check NIVAARAN_AZURE_SPEECH_KEY and _REGION.")
    if r.status_code == 429:
        raise HTTPException(status_code=429, detail="The voice service is busy. Try again in a few seconds.")
    if r.status_code != 200 or not r.content:
        log.warning("Azure speech returned HTTP %s", r.status_code)
        raise HTTPException(status_code=502, detail="The voice service didn't return audio. Try again.")
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)
    return r.content
