"""Natural voice (Azure AI Speech). Azure is simulated here; the app never fakes audio when it isn't configured."""
from fastapi.testclient import TestClient

from app import tts
from app.main import app


class _Resp:
    def __init__(self, status: int, content: bytes = b""):
        self.status_code, self.content = status, content


def _client() -> TestClient:
    c = TestClient(app)
    c.post("/api/demo/user")
    return c


def test_without_a_key_the_voice_is_reported_off_not_faked(monkeypatch):
    monkeypatch.setattr(tts, "KEY", ""); monkeypatch.setattr(tts, "REGION", "")
    c = _client()
    assert c.get("/api/speech").json()["neural"] is False
    r = c.post("/api/speech", json={"text": "नमस्ते", "lang": "hi"})
    assert r.status_code == 503


def test_hindi_and_english_use_neural_voices_and_audio_is_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, "KEY", "k"); monkeypatch.setattr(tts, "REGION", "centralindia"); monkeypatch.setattr(tts, "CACHE", tmp_path)
    calls = []

    def post(url, content=None, headers=None, timeout=None):
        calls.append((url, content.decode("utf-8"), headers))
        return _Resp(200, b"ID3fake-mp3")
    monkeypatch.setattr(tts.httpx, "post", post)
    c = _client()
    r = c.post("/api/speech", json={"text": "चलिए, आपकी पॉलिसी समझते हैं।", "lang": "hi"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3fake-mp3"
    url, ssml, headers = calls[0]
    assert url == "https://centralindia.tts.speech.microsoft.com/cognitiveservices/v1"
    assert "hi-IN-SwaraNeural" in ssml and "xml:lang='hi-IN'" in ssml and headers["Ocp-Apim-Subscription-Key"] == "k"
    c.post("/api/speech", json={"text": "चलिए, आपकी पॉलिसी समझते हैं।", "lang": "hi"})
    assert len(calls) == 1                                           # replay served from cache
    c.post("/api/speech", json={"text": "Here's your policy <in short> & more.", "lang": "en"})
    assert "en-IN-NeerjaNeural" in calls[1][1] and "&lt;in short&gt; &amp; more" in calls[1][1]   # text is escaped in SSML


def test_voice_service_errors_are_explained(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, "KEY", "k"); monkeypatch.setattr(tts, "REGION", "centralindia"); monkeypatch.setattr(tts, "CACHE", tmp_path)
    monkeypatch.setattr(tts.httpx, "post", lambda *a, **k: _Resp(401))
    r = _client().post("/api/speech", json={"text": "hello", "lang": "en"})
    assert r.status_code == 503 and "key" in r.json()["detail"]


def test_speech_requires_sign_in():
    assert TestClient(app).post("/api/speech", json={"text": "hello", "lang": "en"}).status_code == 401
