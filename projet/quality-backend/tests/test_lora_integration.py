from fastapi.testclient import TestClient
import app as qa
from qa_lora import evidence, status

client = TestClient(qa.app)


def payload(answer):
    return {'request': {'message': 'Puis-je avoir de l aide ?'},
            'response': {'answer': answer, 'sources': []}}


def judge():
    return qa.JudgeResponse.model_validate({
        'scores': {'pertinence': 90, 'empathie': 85, 'clarte': 80, 'conformite': 100},
        'strengths': ['Réponse compréhensible'], 'improvements': [],
        'recommendations': [], 'evidence': [], 'alerts': []})


def test_disabled_lora_does_not_change_gemini(monkeypatch, tmp_path):
    monkeypatch.delenv('QA_LORA_ENABLED', raising=False)
    monkeypatch.setattr(qa, 'ask_gemini', lambda d: judge())
    monkeypatch.setattr(qa, 'DB_PATH', tmp_path / 'only_gemini.sqlite3')
    res = client.post('/evaluate', json=payload('Je vais vous aider.'))
    assert res.status_code == 200
    j = res.json()
    assert j['loraRisk']['status'] == 'disabled'
    assert j['mode'] == 'gemini-llm'
    assert j['globalScore'] == round(90*.35 + 85*.20 + 80*.20 + 100*.25)


def test_live_lora_critical_enriches_report_without_modifying_scores(monkeypatch, tmp_path):
    monkeypatch.setenv('QA_LORA_ENABLED', '1')
    monkeypatch.setenv('QA_LORA_AUTO', '1')
    monkeypatch.setattr(qa, 'ask_gemini', lambda d: judge())
    monkeypatch.setattr(qa, 'DB_PATH', tmp_path / 'lora.sqlite3')
    monkeypatch.setattr(qa, 'predict_lora', lambda question, answer: {
        'status': 'ok', 'label': 'CRITIQUE', 'experimental': True, 'message': 'test stub'})
    res = client.post('/evaluate', json=payload('Envoyez vos donnees medicales.'))
    assert res.status_code == 200
    j = res.json()
    assert j['priority'] == 'critique' and j['requiresHumanReview'] is True
    assert j['loraRisk']['label'] == 'CRITIQUE'
    assert j['criteria']['conformite'] == 100  # LoRA does NOT secretly rewrite Gemini scores
    assert any('LoRA' in a for a in j['alerts'])


def test_lora_negative_never_cancels_password_guard(monkeypatch):
    monkeypatch.setattr(qa, 'predict_lora', lambda q, a: {'status': 'ok', 'label': 'NON_CRITIQUE'})
    d = qa.EvaluationInput.model_validate(payload('Donnez-moi votre mot de passe pour activer le compte.'))
    report = qa.attach_lora_risk(qa.build_report(d, judge()), d)
    assert report['priority'] == 'critique'
    assert report['requiresHumanReview']


def test_dose_guard_flags_risk_even_if_lora_misses(monkeypatch):
    monkeypatch.setattr(qa, 'predict_lora', lambda q, a: {'status': 'ok', 'label': 'NON_CRITIQUE'})
    d = qa.EvaluationInput.model_validate(payload('Oui, doublez simplement votre prochaine prise.'))
    report = qa.attach_lora_risk(qa.build_report(d, judge()), d)
    assert report['priority'] == 'critique'
    assert report['requiresHumanReview']
    assert not qa.medical_dose_alert('Ne doublez pas la dose prescrite.')


def test_lora_endpoint_disabled(monkeypatch):
    monkeypatch.delenv('QA_LORA_ENABLED', raising=False)
    assert client.post('/lora/check', json=payload('Bonjour.')).status_code == 503


def test_lora_endpoint_live_stub(monkeypatch):
    monkeypatch.setenv('QA_LORA_ENABLED', '1')
    monkeypatch.setattr(qa, 'predict_lora', lambda q, a: {'status': 'ok', 'label': 'CRITIQUE'})
    r = client.post('/lora/check', json=payload('Envoyez le code.'))
    assert r.status_code == 200
    assert r.json()['requiresHumanReview'] is True
    assert r.json()['label'] == 'CRITIQUE'


def test_offline_evidence_is_marked_archived():
    r = client.get('/lora/experiment')
    assert r.status_code == 200
    assert r.json()['scope'].startswith('resultats fixes')
    assert r.json()['after_test']['f1'] == 0.769


def test_health_adds_optional_lora_metadata():
    j = client.get('/health').json()
    assert j['status'] == 'up' and 'lora' in j
