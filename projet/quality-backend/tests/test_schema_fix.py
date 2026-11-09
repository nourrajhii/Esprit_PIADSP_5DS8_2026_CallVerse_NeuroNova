import io
import json
import pytest
from fastapi import HTTPException

import qa_judge

VALID_OUTPUT = {
    'scores': {'pertinence': 3, 'empathie': 1, 'clarte': 3, 'conformite': 0},
    'risk_label': 'CRITIQUE',
    'reasoning': 'Demande de secrets d authentification.',
    'evidence': [{'criterion': 'conformite', 'quote': 'mot de passe', 'reason': 'Demande de secret.'}],
    'improvements': ['Ne pas demander de secret.'],
    'insufficient_evidence': False,
}


class FakeResp:
    def __init__(self, body):
        self.body = body
    def __enter__(self):
        return io.BytesIO(json.dumps(self.body).encode('utf-8'))
    def __exit__(self, *args):
        return False


def provider_response(output):
    return {'candidates': [{'finishReason': 'STOP',
                            'content': {'parts': [{'text': json.dumps(output, ensure_ascii=False)}]}}]}


def test_schema_explicit_fields_and_validation(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'FAKE_LOCAL_TEST_KEY')
    monkeypatch.setenv('QA_JUDGE_ENABLED', '1')
    captured=[]
    def fake_urlopen(req, timeout):
        data=json.loads(req.data)
        captured.append(data)
        return FakeResp(provider_response(VALID_OUTPUT))
    monkeypatch.setattr(qa_judge, 'urlopen', fake_urlopen)
    out=qa_judge.call_judge_provider('Je ne peux pas me connecter', 'Donnez votre mot de passe', 'inquiet')
    assert out.risk_label == 'CRITIQUE'
    assert len(captured)==1
    schema=captured[0]['generationConfig']['responseSchema']
    assert schema['properties']['risk_label']['enum']==['CRITIQUE', 'NON_CRITIQUE']
    assert 'evidence' in schema['required']
    assert schema['properties']['scores']['required']==list(qa_judge.WEIGHTS)


def test_malformed_then_valid_retry(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','FAKE_LOCAL_TEST_KEY')
    monkeypatch.setenv('QA_JUDGE_ENABLED','1')
    responses=[{'candidates':[{'content':{'parts':[{'text':'not json'}]}}]},
               provider_response(VALID_OUTPUT)]
    calls=[]
    def fake_urlopen(req, timeout):
        calls.append(1)
        return FakeResp(responses.pop(0))
    monkeypatch.setattr(qa_judge, 'urlopen', fake_urlopen)
    out=qa_judge.call_judge_provider('q','réponse','profil')
    assert out.scores.conformite==0
    assert len(calls)==2


def test_persistent_invalid_does_not_invent_score(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','FAKE_LOCAL_TEST_KEY')
    monkeypatch.setenv('QA_JUDGE_ENABLED','1')
    monkeypatch.setattr(qa_judge,'urlopen', lambda req, timeout: FakeResp(provider_response({'scores':{'pertinence':5}})))
    with pytest.raises(HTTPException) as exc:
        qa_judge.call_judge_provider('q','réponse','profil')
    assert exc.value.status_code == 502
    assert 'aucune évaluation' in exc.value.detail


def test_empty_response_does_not_invent_score(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','FAKE_LOCAL_TEST_KEY')
    monkeypatch.setenv('QA_JUDGE_ENABLED','1')
    monkeypatch.setattr(qa_judge,'urlopen',lambda req,timeout: FakeResp({'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[]}}]}))
    with pytest.raises(HTTPException) as exc:
        qa_judge.call_judge_provider('q','r','p')
    assert exc.value.status_code == 502


def test_success_guard_grounding(monkeypatch):
    out=qa_judge.JudgeOutput.model_validate(VALID_OUTPUT)
    summary=qa_judge.format_judge_result('q','Donnez votre mot de passe',out, ['signal sécurité'],34)
    assert summary['status']=='ok'
    assert summary['riskLabel']=='CRITIQUE'
    assert summary['evidenceQuotesVerified']
    assert summary['requiresHumanReview']
