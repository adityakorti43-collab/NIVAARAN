"""Google Gemini (free tier) for read-aloud and translation. Gemini is simulated here; never faked in the app."""
import base64
import json

from fastapi.testclient import TestClient

from app import gemini, translate, tts
from app.main import app


class _Resp:
    def __init__(self, body, status=200):
        self.status_code, self._b, self.text = status, body, ""

    def json(self):
        return self._b


def _client():
    c = TestClient(app); c.post("/api/demo/user"); return c


def test_gemini_reads_aloud_in_a_female_voice_as_wav(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, "KEY", ""); monkeypatch.setattr(tts, "REGION", ""); monkeypatch.setattr(tts, "CACHE", tmp_path)
    monkeypatch.setattr(gemini, "KEY", "g-key")
    sent = []

    def post(url, headers=None, json=None, timeout=None):
        sent.append((url, headers, json))
        pcm = b"\x00\x01" * 2400
        return _Resp({"steps": [{"type": "model_output", "content": [{"type": "audio", "data": base64.b64encode(pcm).decode(), "mime_type": "audio/l16"}]}]})
    monkeypatch.setattr(gemini.httpx, "post", post)
    c = _client()
    assert c.get("/api/speech").json() == {"neural": True, "provider": "gemini"}
    r = c.post("/api/speech", json={"text": "Alright, here's your policy in a nutshell.", "lang": "en"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content[:4] == b"RIFF"
    url, headers, body = sent[0]
    assert url.endswith("/v1beta/interactions") and headers["x-goog-api-key"] == "g-key"
    assert body["model"] == gemini.TTS_MODEL and body["generation_config"]["speech_config"] == [{"voice": "Kore"}]
    c.post("/api/speech", json={"text": "Alright, here's your policy in a nutshell.", "lang": "en"})
    assert len(sent) == 1                                       # cached


def test_gemini_translates_and_keeps_order(monkeypatch):
    monkeypatch.setattr(translate, "KEY", ""); monkeypatch.setattr(translate, "REGION", ""); monkeypatch.setattr(gemini, "KEY", "g-key")
    seen = []

    def post(url, headers=None, json=None, timeout=None):
        seen.append(json)
        texts = __import__("json").loads(json["input"].split("\n\n", 1)[1])
        out = {"translations": [f"[ta] {t}" for t in texts]}
        return _Resp({"steps": [{"type": "model_output", "content": [{"type": "text", "text": __import__("json").dumps(out)}]}]})
    monkeypatch.setattr(gemini.httpx, "post", post)
    c = TestClient(app)
    assert c.get("/api/translate/languages").json()["provider"].startswith("Google Gemini")
    r = c.post("/api/translate", json={"lang": "ta", "texts": ["Room rent cap ₹5,000", "Waiting periods"]}).json()
    assert r["translations"] == ["[ta] Room rent cap ₹5,000", "[ta] Waiting periods"]
    assert "Tamil" in seen[0]["input"] and seen[0]["response_format"]["mime_type"] == "application/json"


def test_gemini_quota_and_bad_key_are_explained(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, "KEY", ""); monkeypatch.setattr(tts, "REGION", ""); monkeypatch.setattr(tts, "CACHE", tmp_path)
    monkeypatch.setattr(gemini, "KEY", "g-key")
    monkeypatch.setattr(gemini.httpx, "post", lambda *a, **k: _Resp({}, 429))
    r = _client().post("/api/speech", json={"text": "hello there", "lang": "en"})
    assert r.status_code == 429 and "quota" in r.json()["detail"]
    monkeypatch.setattr(gemini.httpx, "post", lambda *a, **k: _Resp({}, 403))
    assert _client().post("/api/speech", json={"text": "hello again", "lang": "en"}).status_code == 503
