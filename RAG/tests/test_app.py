from fastapi.testclient import TestClient
from backend.quality.router import EvaluationInput, JudgeResponse, build_report, security_alert
from tests.helper import app

client = TestClient(app)


def sample(answer="Bonjour, je comprends votre problème. Je vais ouvrir un ticket de suivi."):
    return EvaluationInput.model_validate({
        "request": {"profile": "mecontent", "message": "Où est mon colis ?"},
        "response": {"answer": answer, "sources": []}
    })


def judgement():
    return JudgeResponse.model_validate({
        "scores": {"pertinence": 90, "empathie": 80, "clarte": 85, "conformite": 100},
        "strengths": ["La demande est traitée"], "improvements": [],
        "recommendations": ["Fournir un délai"], "evidence": [], "alerts": []
    })


def test_health():
    res = client.get('/api/quality/health')
    assert res.status_code == 200
    assert res.json()['service'] == 'quality-analyst'


def test_score_calculated_from_four_evaluable_criteria():
    r = build_report(sample(), judgement())
    assert r['globalScore'] == round(90 * .35 + 80 * .20 + 85 * .20 + 100 * .25)
    assert r['criteria']['exactitude'] is None
    assert r['criteria']['groundedness'] is None
    assert r['mode'] == 'gemini-llm'


def test_unsafe_credential_request_triggers_alert():
    r = build_report(sample('Donnez-moi votre mot de passe pour vérifier.'), judgement())
    assert r['priority'] == 'critique'
    assert r['requiresHumanReview'] is True
    assert r['criteria']['conformite'] == 10


def test_suspicious_sms_reported_by_client_is_not_advisor_violation():
    assert not security_alert('Ne communiquez jamais votre code secret à un inconnu.')
    assert not security_alert('Notre service ne demandera jamais vos mots de passe.')


def test_no_fake_llm_when_key_missing(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    r = client.post('/api/quality/evaluate', json=sample().model_dump())
    assert r.status_code == 503
    assert 'GEMINI_API_KEY' in r.json()['detail']


def test_invalid_empty_question_rejected():
    r = client.post('/api/quality/evaluate', json={"request": {"message": ""}, "response": {"answer": "Bonjour"}})
    assert r.status_code == 422


def test_real_endpoint_wiring_using_stub_provider(monkeypatch, tmp_path):
    import backend.quality.router as qa
    monkeypatch.setattr(qa, 'DB_PATH', tmp_path / 'test.sqlite3')
    monkeypatch.setattr(qa, 'ask_gemini', lambda payload: judgement())
    response = client.post('/api/agents/quality-analyst', json=sample().model_dump())
    assert response.status_code == 200
    report = response.json()
    assert report['globalScore'] == 90
    assert client.get('/api/quality/kpis').json()['conversationsAnalysees'] == 1
    assert len(client.get('/api/quality/evaluations').json()) == 1


def test_rag_reference_is_injected_into_judge(monkeypatch, tmp_path):
    import backend.quality.router as qa
    seen = {}
    monkeypatch.setattr(qa, 'DB_PATH', tmp_path / 'rag.sqlite3')
    monkeypatch.setattr(qa, 'ask_gemini', lambda payload: seen.update(ref=payload.reference_text) or judgement())
    monkeypatch.setattr(qa, 'RETRIEVER', lambda msg: {"text": "[produit] Creme X, 20 DT", "sources": [{"id": "p1", "title": "Creme X", "score": 0.8}]})
    r = client.post('/api/agents/quality-analyst', json=sample().model_dump())
    assert r.status_code == 200
    assert seen['ref'] == "[produit] Creme X, 20 DT"
    assert r.json()['ragReference']['used'] is True


def test_rag_failure_does_not_block_evaluation(monkeypatch, tmp_path):
    import backend.quality.router as qa
    def boom(msg): raise RuntimeError('index down')
    monkeypatch.setattr(qa, 'DB_PATH', tmp_path / 'rag2.sqlite3')
    monkeypatch.setattr(qa, 'ask_gemini', lambda payload: judgement())
    monkeypatch.setattr(qa, 'RETRIEVER', boom)
    r = client.post('/api/agents/quality-analyst', json=sample().model_dump())
    assert r.status_code == 200 and r.json()['ragReference']['used'] is False
