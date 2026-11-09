from io import BytesIO
from urllib.error import HTTPError
import json

import app as qa


def sample_input():
    return qa.EvaluationInput.model_validate({
        "request": {"message": "Pourquoi ma facture est-elle plus élevée ?"},
        "response": {"answer": "Je vais examiner votre facture avec vous."}
    })


def successful_response():
    data = {"candidates": [{"content": {"parts": [{"text": json.dumps({
        "scores": {"pertinence": 80, "empathie": 70, "clarte": 90, "conformite": 100},
        "strengths": [], "improvements": [], "recommendations": [],
        "evidence": [], "alerts": []
    })}]}}]}
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def read(self, *args):
            return json.dumps(data).encode("utf-8")
    return Response()


def test_retries_503_then_success(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-do-not-use")
    seen=[]
    monkeypatch.setattr(qa.time, "sleep", lambda sec: seen.append(sec))
    calls=[]
    def mock_urlopen(request, timeout):
        calls.append(1)
        if len(calls)<3:
            raise HTTPError("test", 503, "Unavailable", {}, BytesIO(b""))
        return successful_response()
    monkeypatch.setattr(qa, "urlopen", mock_urlopen)
    result=qa.ask_gemini(sample_input())
    assert result.scores.pertinence == 80
    assert len(calls) == 3
    assert len(seen) == 2


def test_retries_stop_after_three_503s(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-do-not-use")
    monkeypatch.setattr(qa.time, "sleep", lambda _: None)
    calls=[]
    def bad_urlopen(request, timeout):
        calls.append(1)
        raise HTTPError("test", 503, "Unavailable", {}, BytesIO(b""))
    monkeypatch.setattr(qa, "urlopen", bad_urlopen)
    try:
        qa.ask_gemini(sample_input())
        assert False, "Expected error"
    except qa.HTTPException as exc:
        assert exc.status_code == 503
        assert "3 tentatives" in exc.detail
    assert len(calls)==3


def test_nonretryable_400(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-do-not-use")
    calls=[]
    def bad_urlopen(request, timeout):
        calls.append(1)
        raise HTTPError("test", 400, "Bad Request", {}, BytesIO(b""))
    monkeypatch.setattr(qa, "urlopen", bad_urlopen)
    try:
        qa.ask_gemini(sample_input())
        assert False, "Expected error"
    except qa.HTTPException as exc:
        assert exc.status_code == 503
    assert len(calls)==1
