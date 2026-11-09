"""Tests de l'étape 7 : explainer LLM, testé HORS LIGNE avec un faux client.

Lancement : python -m pytest workforce_manager/tests -v
"""

import json

import pytest

from workforce_manager.llm import explainer as ex
from workforce_manager.llm.verifications import erreurs_a_plat, verifier
from workforce_manager.micro.quality_rules import decide
from workforce_manager.schemas import QualityEvaluation, WorkforceDecision

EVALUATION = QualityEvaluation(globalScore=55, criteria=dict(
    pertinence=80, exactitude=45, groundedness=40, empathie=50, clarte=80, conformite=80))
DECISION = decide(EVALUATION, "sante")          # relancer_rag + signaler_kb (haute), formation (moyenne)


class FauxClient:
    """Renvoie des réponses prédéfinies (texte ou exception) et garde les appels."""

    def __init__(self, *reponses):
        self.reponses, self.appels = list(reponses), []

    def generer(self, systeme, messages):
        self.appels.append(messages)
        reponse = self.reponses.pop(0)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse


def sortie_valide(decision: WorkforceDecision = DECISION, **modifs) -> dict:
    """Sortie correcte : textes neutres, id/type/priorité recopiés."""
    sortie = {
        "problems": [f"Constat numéro {i} expliqué au chef de plateau." for i in range(len(decision.problems))],
        "actions": [{"id": i, "type": a.type, "priority": a.priority,
                     "description": f"Action numéro {i} à mener selon la consigne reçue."}
                    for i, a in enumerate(decision.actions, start=1)],
    }
    sortie.update(modifs)
    return sortie


def lancer(*reponses, decision=DECISION):
    client = FauxClient(*reponses)
    return ex.expliquer(decision, EVALUATION, "sante", "fidele", {}, client=client, attente_base=0), client


# --------------------------------------------------------------------------- prompt

def test_prompt_et_exemples_charges():
    systeme, exemples = ex.charger_prompt()
    for consigne in ("NE DÉCIDES RIEN", "EXACTEMENT", "conseil médical", "UNIQUEMENT"):
        assert consigne in systeme
    assert [e["nom"].split("_")[0] for e in exemples] == ["sami", "ines", "karim"]


def test_les_exemples_few_shot_respectent_les_verifications():
    for e in ex.charger_prompt()[1]:
        assert erreurs_a_plat(verifier(e["entree"], e["sortie"])) == [], e["nom"]


def test_messages_few_shot_puis_cas_reel():
    entree = ex.construire_entree(DECISION, EVALUATION, "sante", None, None)
    messages = ex.construire_messages(entree, ex.charger_prompt()[1])
    assert [r for r, _ in messages] == ["user", "model"] * 3 + ["user"]
    assert json.loads(messages[-1][1])["actions"][0]["id"] == 1


# --------------------------------------------------------------------------- chemin nominal

def test_sortie_valide_utilisee():
    resultat, client = lancer(json.dumps(sortie_valide()))
    assert resultat.source == "llm" and resultat.tentatives == 1 and len(client.appels) == 1
    assert [a.description for a in resultat.decision.actions][0].startswith("Action numéro 1")
    assert [(a.type, a.priority) for a in resultat.decision.actions] == \
           [(a.type, a.priority) for a in DECISION.actions]
    WorkforceDecision.model_validate(resultat.decision.model_dump())     # contrat respecté


def test_json_entoure_de_balises_markdown():
    resultat, _ = lancer("Voici :\n```json\n" + json.dumps(sortie_valide()) + "\n```")
    assert resultat.source == "llm"


# --------------------------------------------------------------------------- retry puis succès

def test_json_invalide_puis_corrige():
    resultat, client = lancer("{pas du json", json.dumps(sortie_valide()))
    assert resultat.source == "llm" and resultat.tentatives == 2
    assert "invalide" in client.appels[1][-1][1]            # message de correction envoyé
    assert resultat.erreurs[0].startswith("json")


def test_erreur_api_puis_succes():
    resultat, _ = lancer(TimeoutError("réseau"), json.dumps(sortie_valide()))
    assert resultat.source == "llm" and resultat.erreurs[0].startswith("api")


# --------------------------------------------------------------------------- fallback

def test_action_inventee_rejetee_puis_fallback():
    mauvaise = sortie_valide()
    mauvaise["actions"][0]["description"] = "Transférer le client au pharmacien conseil sans attendre."
    resultat, client = lancer(*[json.dumps(mauvaise)] * 3)
    assert resultat.source == "fallback" and len(client.appels) == 3
    assert resultat.decision == DECISION                      # textes fixes de l'étape 6
    assert any("actions_inventees" in e for e in resultat.erreurs)


def test_priorite_modifiee_rejetee():
    mauvaise = sortie_valide()
    mauvaise["actions"][2]["priority"] = "haute"
    resultat, _ = lancer(*[json.dumps(mauvaise)] * 3)
    assert resultat.source == "fallback" and any("priorites" in e for e in resultat.erreurs)


def test_action_supprimee_rejetee():
    mauvaise = sortie_valide()
    mauvaise["actions"] = mauvaise["actions"][:2]
    resultat, _ = lancer(*[json.dumps(mauvaise)] * 3)
    assert resultat.source == "fallback" and any("structure" in e for e in resultat.erreurs)


def test_api_toujours_en_panne():
    resultat, _ = lancer(*[ConnectionError("indisponible")] * 3)
    assert resultat.source == "fallback" and resultat.decision == DECISION


class ErreurHttp(Exception):
    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


def test_erreur_definitive_pas_de_nouvel_essai():
    """404 (modèle inconnu) : inutile de réessayer, textes fixes tout de suite."""
    resultat, client = lancer(ErreurHttp(404), json.dumps(sortie_valide()))
    assert resultat.source == "fallback" and len(client.appels) == 1


def test_quota_429_reessaye():
    resultat, client = lancer(ErreurHttp(429), json.dumps(sortie_valide()))
    assert resultat.source == "llm" and len(client.appels) == 2


class QuotaJournalier(ErreurHttp):
    """429 réel de Gemini quand le quota gratuit du jour est épuisé."""

    def __str__(self):
        return "429 RESOURCE_EXHAUSTED {'@type': 'RetryInfo', 'retryDelay': '52494s'}"


def test_quota_journalier_epuise_pas_de_nouvel_essai():
    resultat, client = lancer(QuotaJournalier(429), json.dumps(sortie_valide()))
    assert resultat.source == "fallback" and len(client.appels) == 1


def test_sans_cle_api(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    resultat = ex.expliquer(DECISION, EVALUATION, "sante")
    assert resultat.source == "fallback" and resultat.tentatives == 0


def test_rien_a_expliquer_pas_d_appel():
    client = FauxClient()
    resultat = ex.expliquer(WorkforceDecision(problems=[], actions=[]), client=client)
    assert resultat.source == "sans_objet" and client.appels == []


# --------------------------------------------------------------------------- vérifications unitaires

def _entree():
    return ex.construire_entree(DECISION, EVALUATION, "sante", None, None)


def test_verif_ton_urgent_sur_priorite_moyenne():
    sortie = sortie_valide()
    sortie["actions"][2]["description"] = "Lancer immédiatement le module pour toute l'équipe."
    assert verifier(_entree(), sortie)["ton_priorite"]


def test_verif_longueur():
    sortie = sortie_valide()
    sortie["problems"][0] = "Trop court"
    sortie["actions"][0]["description"] = "x" * 300
    assert len(verifier(_entree(), sortie)["longueur"]) == 2


def test_verif_dosage_interdit():
    sortie = sortie_valide()
    sortie["problems"][0] = "Le client aurait dû prendre 500 mg deux fois par jour selon la fiche."
    assert verifier(_entree(), sortie)["conseil_medical"]


def test_verif_sortie_conforme_sans_erreur():
    assert erreurs_a_plat(verifier(_entree(), sortie_valide())) == []
