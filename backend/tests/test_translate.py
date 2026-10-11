"""Site translation (Azure AI Translator, simulated here). Never faked when not configured; cached once translated."""
from fastapi.testclient import TestClient

from app import translate
from app.main import app


class _Resp:
    def __init__(self, status, body=None):
        self.status_code, self._body, self.text = status, body, ""

    def json(self):
        return self._body


def test_languages_cover_india_and_report_when_off(monkeypatch):
    monkeypatch.setattr(translate, "KEY", ""); monkeypatch.setattr(translate, "REGION", "")
    c = TestClient(app)
    info = c.get("/api/translate/languages").json()
    codes = {l["code"] for l in info["languages"]}
    assert info["enabled"] is False and {"hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "or", "pa", "as", "ur", "ks", "sd", "mni", "brx", "doi", "gom", "mai", "ne"} <= codes
    assert c.post("/api/translate", json={"lang": "ta", "texts": ["Hello"]}).status_code == 503
    assert c.post("/api/translate", json={"lang": "en", "texts": ["Hello"]}).json()["translations"] == ["Hello"]


def test_translations_are_cached_and_deduplicated(monkeypatch):
    monkeypatch.setattr(translate, "KEY", "k"); monkeypatch.setattr(translate, "REGION", "centralindia")
    calls = []

    def post(url, params=None, headers=None, json=None, timeout=None):
        calls.append((params["to"], [x["Text"] for x in json], headers["Ocp-Apim-Subscription-Region"]))
        return _Resp(200, [{"translations": [{"text": f"[{params['to']}] {x['Text']}"}]} for x in json])
    monkeypatch.setattr(translate.httpx, "post", post)
    c = TestClient(app)
    r = c.post("/api/translate", json={"lang": "bn", "texts": ["Room rent cap", "Room rent cap", "Sum insured"]}).json()
    assert r["translations"] == ["[bn] Room rent cap", "[bn] Room rent cap", "[bn] Sum insured"]
    assert calls == [("bn", ["Room rent cap", "Sum insured"], "centralindia")]       # each unique string once
    c.post("/api/translate", json={"lang": "bn", "texts": ["Sum insured"]})
    assert len(calls) == 1                                                           # served from the cache
    assert c.post("/api/translate", json={"lang": "ur", "texts": ["x"]}).json()["rtl"] is True


def test_unknown_language_rejected():
    assert TestClient(app).post("/api/translate", json={"lang": "xx", "texts": ["a"]}).status_code == 422
