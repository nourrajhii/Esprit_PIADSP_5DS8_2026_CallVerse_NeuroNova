from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routes import simulation as routes
from backend.services import history, simulation

app = FastAPI()
app.include_router(routes.router)
client = TestClient(app)


def fake_conversation(*, message_count, first_message, **_):
    turns = [{"turn": i + 1, "clientMessage": first_message or f"question {i + 1}", "clientLatencyMs": 5,
              "advisor": {"answer": f"réponse {i + 1}", "latencyMs": 100, "intent": "facturation",
                          "sources": [{"id": "s1", "title": "Fiche", "score": 0.8, "snippet": "texte"}]}}
             for i in range(message_count)]
    return {"id": "sim1", "createdAt": "2026-10-28T10:00:00+00:00", "client": {"name": "A B"},
            "clientModel": "qwen", "advisorModel": "gpt", "turns": turns}


def fake_report(conv_id, profile, turn):
    bad = turn["turn"] == 2
    return {"globalScore": 50 if bad else 90, "criteria": {"pertinence": 80, "exactitude": None, "groundedness": None,
            "empathie": 40 if bad else 90, "clarte": 80, "conformite": 90}, "strengths": ["clair"], "improvements": ["empathie"],
            "recommendations": [], "alerts": ["ALERTE"] if bad else [], "priority": "critique" if bad else "faible",
            "requiresHumanReview": bad, "accuracyStatus": "Non vérifiable", "loraRisk": {"status": "disabled"}}


def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(history, "FILE", tmp_path / "sims.json")
    monkeypatch.setattr(routes, "run_conversation", fake_conversation)
    monkeypatch.setattr(simulation, "_evaluate_turn", fake_report)
    monkeypatch.setattr(simulation, "save_to_db", lambda conv: False)


def test_single_simulation_has_front_shape_and_is_listed(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path)
    r = client.post("/api/simulations", json={"profile": "calme", "message": "Bonjour", "conversationMode": False, "messageCount": 1})
    assert r.status_code == 201
    d = r.json()
    assert d["isConversation"] is False and d["request"]["message"] == "Bonjour"
    assert d["response"]["sources"][0]["title"] == "Fiche"
    assert d["evaluation"]["globalScore"] == 90 and d["decision"]["status"] == "OPTIMAL"
    assert client.get("/api/conversations").json()[0]["id"] == "sim1"
    assert client.get("/api/simulations/sim1").json()["score"] == 90
    assert client.get("/api/simulations/nope").status_code == 404


def test_conversation_aggregates_turns_and_escalates(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path)
    d = client.post("/api/simulations/conversation", json={"profile": "mecontent", "messageCount": 3}).json()
    assert d["isConversation"] and len(d["exchanges"]) == 3
    assert d["evaluation"]["globalScore"] == 77 and d["evaluation"]["criteria"]["exactitude"] is None
    assert d["evaluation"]["priority"] == "critique" and d["evaluation"]["requiresHumanReview"]
    assert d["decision"]["status"] == "INTERVENTION_REQUISE"
    assert d["decision"]["actions"][0]["type"] == "escalade_humain"
