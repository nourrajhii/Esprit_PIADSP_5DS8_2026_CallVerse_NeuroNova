"""Tests de l'étape 8 : API FastAPI (TestClient, sans serveur, sans appel réseau).

Lancement : python -m pytest workforce_manager/tests/test_api.py -v
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from workforce_manager.api import simulation
from workforce_manager.api.main import app, client_llm
from workforce_manager.policies.ppo import FICHIER_PPO, FICHIER_PPO_GENERAL
from workforce_manager.policies.q_learning import FICHIER_Q_TABLE
from workforce_manager.schemas import Kpi, MockEvaluationRecord, WorkforceDecision, WorkforceDecisionEtendue

URL_DECISION = "/api/agents/workforce-manager"
URL_SIMULATION = "/api/agents/workforce-manager/simulate-day"
EXEMPLES = Path(__file__).parent.parent / "api" / "exemples"


def exemple(nom: str) -> dict:
    return json.loads((EXEMPLES / f"{nom}.json").read_text(encoding="utf-8"))


class FauxLLM:
    """Réécrit chaque texte proprement, ou lève une erreur si en_panne."""

    def __init__(self, en_panne: bool = False):
        self.en_panne, self.appels = en_panne, 0

    def generer(self, systeme, messages):
        self.appels += 1
        if self.en_panne:
            raise ConnectionError("Gemini indisponible")
        entree = json.loads(messages[-1][1])
        return json.dumps({
            "problems": [f"Problème {i} reformulé pour le chef de plateau." for i in range(len(entree["constats"]))],
            "actions": [{**{k: a[k] for k in ("id", "type", "priority")},
                         "description": f"Consigne {a['id']} détaillée pour l'équipe du centre."}
                        for a in entree["actions"]],
        })


@pytest.fixture
def client():
    """Client de test avec LLM désactivé par défaut (aucun appel réseau) et KPI remis à zéro."""
    app.dependency_overrides[client_llm] = lambda: FauxLLM(en_panne=True)
    app.state.derniers_kpi = None
    yield TestClient(app)
    app.dependency_overrides.clear()


def types_actions(reponse) -> list:
    return [a["type"] for a in reponse.json()["actions"]]


# --------------------------------------------------------------------------- POST /agents/workforce-manager

@pytest.mark.parametrize("persona, attendu", [
    ("sami", ["relancer_rag", "signaler_kb", "formation"]),
    ("ines", ["escalade_humain", "formation"]),
    ("karim", ["escalade_humain", "relancer_rag", "signaler_kb"]),
])
def test_personas(client, persona, attendu):
    r = client.post(URL_DECISION, json=exemple(persona))
    assert r.status_code == 200
    WorkforceDecisionEtendue.model_validate(r.json())           # réponse étendue (front)
    assert types_actions(r) == attendu
    strict = client.post(URL_DECISION, json=exemple(persona), params={"strict": "true"})
    WorkforceDecision.model_validate(strict.json())             # conforme au contrat


def test_contrat_strict_sans_type_demande(client):
    """Requête exactement au format du Swagger actuel : acceptée (précaution santé)."""
    r = client.post(URL_DECISION, json={"evaluation": exemple("ines")["evaluation"]})
    assert r.status_code == 200 and "escalade_humain" in types_actions(r)


def test_mode_strict_sans_champ_hors_contrat(client):
    r = client.post(URL_DECISION, json=exemple("karim"), params={"strict": "true"})
    assert set(r.json()) == {"problems", "actions"}
    assert all(set(a) == {"type", "description", "priority"} for a in r.json()["actions"])


def test_llm_redige_mais_ne_decide_pas(client):
    app.dependency_overrides[client_llm] = lambda: FauxLLM()
    sans_llm = client.post(URL_DECISION, json=exemple("sami"), params={"explications": "false"}).json()
    r = client.post(URL_DECISION, json=exemple("sami"))
    assert r.headers["X-Explication-Source"] == "llm"
    assert r.json()["actions"][0]["description"].startswith("Consigne 1")
    assert [(a["type"], a["priority"]) for a in r.json()["actions"]] == \
           [(a["type"], a["priority"]) for a in sans_llm["actions"]]


def test_llm_en_panne_textes_fixes(client):
    r = client.post(URL_DECISION, json=exemple("sami"))
    assert r.status_code == 200 and r.headers["X-Explication-Source"] == "fallback"
    assert r.json()["actions"][0]["description"].startswith("Relancer la recherche")


def test_explications_desactivees_sans_appel_llm(client):
    faux = FauxLLM()
    app.dependency_overrides[client_llm] = lambda: faux
    r = client.post(URL_DECISION, json=exemple("ines"), params={"explications": "false"})
    assert r.headers["X-Explication-Source"] == "desactive" and faux.appels == 0


def test_bonne_reponse_aucune_action(client):
    criteres = dict(pertinence=90, exactitude=90, groundedness=90, empathie=90, clarte=90, conformite=90)
    r = client.post(URL_DECISION, json={"evaluation": {"globalScore": 90, "criteria": criteres}, "type_demande": "sante"})
    assert r.json()["problems"] == [] and r.json()["actions"] == []
    assert r.json()["status"] == "OPTIMAL"
    assert r.headers["X-Explication-Source"] == "sans_objet"


@pytest.mark.parametrize("corps", [
    {"evaluation": {"globalScore": 150}},                                  # hors bornes 0-100
    {"evaluation": {"globalScore": 70}, "type_demande": "pharmacie"},      # type inconnu
    {"evaluation": {"globalScore": 70, "champInconnu": 1}},               # champ hors contrat
    {"evaluation": {"criteria": {"empathie": "bof"}}},                    # mauvais type
])
def test_requetes_invalides_422_format_error(client, corps):
    r = client.post(URL_DECISION, json=corps)
    assert r.status_code == 422
    assert set(r.json()) == {"code", "message"} and r.json()["code"] == "requete_invalide"


def test_corps_absent_422(client):
    assert client.post(URL_DECISION).status_code == 422


def test_les_200_mocks_passent_par_l_api(client):
    mocks = json.loads((Path(__file__).parent.parent / "data" / "mock_evaluations.json").read_text(encoding="utf-8"))
    for m in map(MockEvaluationRecord.model_validate, mocks):
        corps = {"evaluation": m.evaluation.model_dump(exclude_none=True), "type_demande": m.type_demande}
        r = client.post(URL_DECISION, json=corps, params={"explications": "false"})
        assert r.status_code == 200, m.id
        WorkforceDecisionEtendue.model_validate(r.json())


# --------------------------------------------------------------------------- intégration avec le front de l'équipe

KPI_DU_FRONT = {"qualiteReponses": 82.4, "tauxResolution": 76.1, "tempsTraitementSec": 4.2, "tauxEscalade": 8.5,
                "satisfactionClient": 4.1, "performanceParProfil": [{"profile": "calme", "score": 80, "count": 12}]}
REQUETE_DU_FRONT = {   # exactement ce qu'envoie WorkforceManagerPage.jsx (dt-front)
    "evaluation": {"globalScore": 62, "criteria": {"empathie": 55, "groundedness": 60}},
    "request": {"profile": "mecontent"},
    "kpi": KPI_DU_FRONT,
}


@pytest.mark.parametrize("kpi", [KPI_DU_FRONT, None])
def test_requete_exacte_du_front_acceptee(client, kpi):
    r = client.post(URL_DECISION, json={**REQUETE_DU_FRONT, "kpi": kpi})
    assert r.status_code == 200


def test_reponse_contient_ce_que_lit_la_page_du_front(client):
    corps = client.post(URL_DECISION, json=REQUETE_DU_FRONT).json()
    assert corps["status"] in {"OPTIMAL", "INTERVENTION_REQUISE"}
    assert corps["auditScore"] == 62 and corps["agent"] == "Workforce Manager Agent"
    assert set(corps["workforceSummary"]) == {"staffingImpact", "trainingModuleSuggested", "kbUpdateRequired"}
    assert all(a["responsible"] for a in corps["actions"])


@pytest.mark.parametrize("corps, attendu, source", [
    ({"type_demande": "standard", "request": {"message": "urgence enfant"}}, "standard", "type_demande"),
    ({"request": {"entities": {"type_demande": "sante"}}}, "sante", "request.entities"),
    ({"request": {"message": "Mon fils a avalé des comprimés, c'est urgent"}}, "urgence", "request.message"),
    ({"request": {"intent": "question_posologie"}}, "sante", "request.intent"),
    ({"request": {"intent": "suivi_commande", "message": "Où est mon colis ?"}}, "standard",
     "request.sans_mot_cle"),
    ({"request": {"profile": "calme"}}, None, "inconnu"),
])
def test_type_demande_deduit_et_trace(client, corps, attendu, source):
    r = client.post(URL_DECISION, json={"evaluation": {"globalScore": 70}, **corps},
                    params={"explications": "false"})
    assert r.headers["X-Type-Demande-Source"] == source
    assert r.json().get("typeDemande") == attendu


@pytest.mark.parametrize("type_demande, responsable", [
    ("sante", "Pharmacien conseil"), ("urgence", "Superviseur de plateau (urgence)"),
    ("standard", "Superviseur équipe N2"),
])
def test_responsable_escalade_selon_le_type(client, type_demande, responsable):
    corps = {"evaluation": {"globalScore": 50, "criteria": {"pertinence": 30, "conformite": 40}},
             "type_demande": type_demande}
    actions = client.post(URL_DECISION, json=corps, params={"explications": "false"}).json()["actions"]
    escalades = [a for a in actions if a["type"] == "escalade_humain"]
    if type_demande == "standard":     # en standard, pas d'escalade : correction de la réponse
        assert not escalades
    else:
        assert escalades[0]["responsible"] == responsable


def test_statut_suit_la_decision_et_non_le_score(client):
    """85/100 mais non conforme sur la santé : intervention requise malgré le bon score."""
    corps = {"evaluation": {"globalScore": 85, "criteria": {"conformite": 50}}, "type_demande": "sante"}
    assert client.post(URL_DECISION, json=corps, params={"explications": "false"}).json()["status"] == \
        "INTERVENTION_REQUISE"


def test_wm_llm_off_desactive_le_llm_par_defaut(client, monkeypatch):
    faux = FauxLLM()
    app.dependency_overrides[client_llm] = lambda: faux
    monkeypatch.setenv("WM_LLM", "off")
    r = client.post(URL_DECISION, json=REQUETE_DU_FRONT)
    assert r.headers["X-Explication-Source"] == "desactive" and faux.appels == 0
    r = client.post(URL_DECISION, json=REQUETE_DU_FRONT, params={"explications": "true"})   # forçage explicite
    assert r.headers["X-Explication-Source"] == "llm"


def test_kpi_mal_forme_refuse(client):
    r = client.post(URL_DECISION, json={**REQUETE_DU_FRONT, "kpi": {"tauxEscalade": "beaucoup"}})
    assert r.status_code == 422


# --------------------------------------------------------------------------- simulate-day et GET /kpi

def test_kpi_404_avant_toute_simulation(client):
    r = client.get("/api/kpi")
    assert r.status_code == 404 and r.json()["code"] == "aucune_simulation"


def test_simulation_sami_sans_pilotage(client):
    r = client.post(URL_SIMULATION, json={"scenario": "sami_rupture_stock", "policy": "none"})
    assert r.status_code == 200
    corps = r.json()
    assert len(corps["steps"]) == 48 and corps["steps"][-1]["heure"] == "20h00"
    Kpi.model_validate(corps["kpi"])                             # format Kpi du Swagger
    assert corps["kpi"]["tauxResolution"] == pytest.approx(100 * corps["indicateurs"]["fcr"], abs=0.1)   # FCR
    assert 1 <= corps["kpi"]["satisfactionClient"] <= 5


def test_kpi_de_la_derniere_simulation(client):
    simu = client.post(URL_SIMULATION, json={"scenario": "journee_normale", "policy": "rules", "seed": 3}).json()
    assert client.get("/api/kpi").json() == simu["kpi"]


def test_simulation_reproductible(client):
    corps = {"scenario": "karim_retour_sensible", "policy": "random", "seed": 7}
    assert client.post(URL_SIMULATION, json=corps).json() == client.post(URL_SIMULATION, json=corps).json()


def test_les_regles_font_mieux_que_rien(client):
    def abandons(policy):
        r = client.post(URL_SIMULATION, json={"scenario": "sami_rupture_stock", "policy": policy})
        return r.json()["indicateurs"]["taux_abandon"]
    assert abandons("rules") < abandons("none")


@pytest.mark.parametrize("corps", [
    {"scenario": "sami_rupture_stock", "policy": "dqn"},
    {"scenario": "inconnu", "policy": "rules"},
    {"scenario": "sami_rupture_stock", "policy": "rules", "seed": -1},
])
def test_simulation_requete_invalide(client, corps):
    assert client.post(URL_SIMULATION, json=corps).status_code == 422


@pytest.mark.skipif(not (FICHIER_PPO.exists() and FICHIER_Q_TABLE.exists() and FICHIER_PPO_GENERAL.exists()),
                    reason="modèles RL non entraînés")
@pytest.mark.parametrize("policy", ["qlearning", "ppo", "ppo_standard"])
def test_simulation_politiques_rl(client, policy):
    r = client.post(URL_SIMULATION, json={"scenario": "ines_urgence_heure_pointe", "policy": policy})
    assert r.status_code == 200 and len(r.json()["steps"]) == 48


def test_ppo_par_defaut_est_le_generaliste():
    """policy "ppo" -> modèle généraliste ; "ppo_standard" -> ancien modèle (étape 5)."""
    assert simulation.NOMS_INTERNES["ppo"] == "ppo_general"
    assert simulation.NOMS_INTERNES["ppo_standard"] == "ppo"


def test_ancien_nom_ppo_general_refuse(client):
    r = client.post(URL_SIMULATION, json={"scenario": "sami_rupture_stock", "policy": "ppo_general"})
    assert r.status_code == 422


def test_modele_absent_503(client, monkeypatch):
    def absent(policy):
        raise simulation.ModeleNonEntraine("Modèle 'ppo' introuvable")
    monkeypatch.setattr("workforce_manager.api.main.simuler_journee",
                        lambda scenario, policy, seed: absent(policy))
    r = client.post(URL_SIMULATION, json={"scenario": "sami_rupture_stock", "policy": "ppo"})
    assert r.status_code == 503 and r.json()["code"] == "modele_non_entraine"


# --------------------------------------------------------------------------- CORS et documentation

def test_cors_front_autorise(client):
    r = client.options(URL_DECISION, headers={"Origin": "http://localhost:5173",
                                              "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_autre_origine_refusee(client):
    r = client.options(URL_DECISION, headers={"Origin": "http://evil.example",
                                              "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in r.headers


def test_documentation_openapi(client):
    doc = client.get("/openapi.json").json()
    assert {URL_DECISION, URL_SIMULATION, "/api/kpi"} <= set(doc["paths"])
    erreur_422 = doc["paths"][URL_DECISION]["post"]["responses"]["422"]
    assert erreur_422["content"]["application/json"]["schema"]["$ref"].endswith("/Error")
