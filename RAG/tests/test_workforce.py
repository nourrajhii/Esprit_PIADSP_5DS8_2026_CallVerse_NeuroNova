from fastapi.testclient import TestClient

from backend.routes.workforce import router
from fastapi import FastAPI

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def decide(evaluation, profile="calme", kpi=None):
    r = client.post("/api/agents/workforce-manager", json={"evaluation": evaluation, "request": {"profile": profile}, "kpi": kpi})
    assert r.status_code == 200
    return r.json()


def test_good_score_is_optimal():
    d = decide({"globalScore": 90, "criteria": {"empathie": 90, "groundedness": 90}})
    assert d["status"] == "OPTIMAL" and d["problems"] == []
    assert [a["type"] for a in d["actions"]] == ["formation"]


def test_low_scores_trigger_actions():
    d = decide({"globalScore": 60, "criteria": {"empathie": 50, "groundedness": 50}}, "mecontent")
    types = [a["type"] for a in d["actions"]]
    assert d["status"] == "INTERVENTION_REQUISE"
    assert {"escalade_humain", "ajuster_reponse", "signaler_kb", "formation"} <= set(types)
    assert d["workforceSummary"]["kbUpdateRequired"] is True


def test_unverified_criterion_is_not_penalised():
    d = decide({"globalScore": 85, "criteria": {"empathie": 85, "groundedness": None, "exactitude": None}})
    assert d["status"] == "OPTIMAL" and d["workforceSummary"]["kbUpdateRequired"] is False


def test_critical_quality_alert_escalates_even_with_high_score():
    d = decide({"globalScore": 88, "criteria": {"empathie": 90}, "priority": "critique", "requiresHumanReview": True,
                "alerts": ["ALERTE CRITIQUE : secret demandé"]})
    assert d["status"] == "INTERVENTION_REQUISE"
    assert d["actions"][0]["type"] == "escalade_humain" and d["actions"][0]["priority"] == "haute"
    assert "ALERTE CRITIQUE : secret demandé" in d["problems"]


def test_lora_critical_label_escalates():
    d = decide({"globalScore": 88, "criteria": {}, "loraRisk": {"status": "ok", "label": "CRITIQUE"}})
    assert d["status"] == "INTERVENTION_REQUISE"


def test_kpi_empty_and_computed(tmp_path, monkeypatch):
    import json, sqlite3
    import backend.quality.router as qa
    monkeypatch.setattr(qa, "DB_PATH", tmp_path / "q.sqlite3")
    assert client.get("/api/kpi").json()["evaluations"] == 0
    with sqlite3.connect(qa.DB_PATH) as conn:
        conn.execute("CREATE TABLE evaluations (id TEXT PRIMARY KEY, evaluated_at TEXT, global_score INTEGER, report_json TEXT)")
        for i, (score, review, prof) in enumerate([(90, False, "calme"), (50, True, "mecontent")]):
            rep = {"globalScore": score, "requiresHumanReview": review, "profile": prof}
            conn.execute("INSERT INTO evaluations VALUES (?,?,?,?)", (str(i), "2026", score, json.dumps(rep)))
    k = client.get("/api/kpi").json()
    assert k["qualiteReponses"] == 70 and k["tauxEscalade"] == 50 and k["tauxResolution"] == 50
    assert {p["profile"] for p in k["performanceParProfil"]} == {"calme", "mecontent"}
