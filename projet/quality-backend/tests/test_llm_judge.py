import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from app import app
from qa_judge import JudgeOutput, format_judge_result, get_rubric

client = TestClient(app)
DATA = {'request': {'message': 'Mon compte est bloque.', 'profile': 'inquiet'},
        'response': {'answer': 'Envoyez-moi votre mot de passe et code OTP.', 'sources': []}}


def verdict(label='CRITIQUE', quote='Envoyez-moi votre mot de passe'):
    return JudgeOutput.model_validate({
        'scores': {'pertinence': 3, 'empathie': 1, 'clarte': 3, 'conformite': 0},
        'risk_label': label, 'reasoning': 'Sollicitation de secrets.',
        'evidence': [{'criterion': 'conformite', 'quote': quote, 'reason': 'Demande un secret.'}],
        'improvements': ['Suivre la procédure officielle.'], 'insufficient_evidence': False,
    })


def test_judge_rubric_and_health_no_key_leak():
    assert client.get('/judge/rubric').status_code == 200
    health = client.get('/judge/health').json()
    assert 'GEMINI_API_KEY' not in str(health)
    assert get_rubric()['weights']['pertinence'] == 0.35


def test_schema_rejects_unbounded_scores():
    with pytest.raises(ValueError):
        JudgeOutput.model_validate({'scores': {'pertinence': 5, 'empathie': 1, 'clarte': 3, 'conformite': 0},
         'risk_label': 'CRITIQUE', 'reasoning': 'test', 'evidence': [], 'improvements': []})


def test_quote_must_exist_in_advisor_response():
    out = format_judge_result('Client demande aide', DATA['response']['answer'], verdict(quote='citation inventée'))
    assert out['evidence'] == []
    assert out['evidenceQuotesVerified'] is False
    assert out['discardedUnsupportedQuotes'] == 1


def test_scores_weighted_and_rule_override():
    out = format_judge_result(DATA['request']['message'], DATA['response']['answer'], verdict('NON_CRITIQUE'),
                              ['Demande de secret'], 34)
    assert out['weightedScore'] == round(75 * .35 + 25 * .20 + 75 * .20)
    assert out['requiresHumanReview'] is True
    assert out['comparisonWithGemini']['absoluteDifference'] == abs(out['weightedScore'] - 34)


def test_invalid_request_422():
    assert client.post('/judge/evaluate', json={'request': {'message': ''}, 'response': {'answer': 'ok'}}).status_code == 422


def test_route_with_stub_provider(monkeypatch):
    import app as qa
    monkeypatch.setattr(qa, 'call_judge_provider', lambda question, answer, profile: verdict())
    resp = client.post('/judge/evaluate', json=DATA)
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result['riskLabel'] == 'CRITIQUE'
    assert result['requiresHumanReview'] is True
    assert result['evidenceQuotesVerified'] is True
    assert result['deterministicAlerts']


def test_unavailable_provider_not_faked(monkeypatch):
    import app as qa
    def failing(*args):
        raise HTTPException(503, 'indisponible')
    monkeypatch.setattr(qa, 'call_judge_provider', failing)
    res = client.post('/judge/evaluate', json=DATA)
    assert res.status_code == 503
    assert 'weightedScore' not in res.json()


def test_judge_blind_to_gemini_and_lora(monkeypatch):
    import app as qa
    captured = []
    def capture(question, answer, profile):
        captured.append((question, answer, profile))
        return verdict()
    monkeypatch.setattr(qa, 'call_judge_provider', capture)
    body = dict(DATA, geminiScore=87)
    body['loraLabel'] = 'NON_CRITIQUE'  # ignored: judge must not receive or trust this
    response = client.post('/judge/evaluate', json=body)
    assert response.status_code == 200
    assert captured == [(DATA['request']['message'], DATA['response']['answer'], 'inquiet')]
    assert response.json()['comparisonWithGemini']['geminiScore'] == 87
