"""Tests de la couche « agent responsable » : masquage, validation humaine, inconnu, journal.

Lancement : python -m pytest workforce_manager/tests/test_responsable.py -v
"""

import copy

import numpy as np
import pytest

from workforce_manager.env.call_center_env import ACTIONS, FAMILLES_EVENEMENTS, NOMS_ETAT, CallCenterEnv
from workforce_manager.env.random_scenarios import generer_scenario
from workforce_manager.evaluation.run_policy import jouer_journee
from workforce_manager.policies.ppo import FICHIER_PPO_GENERAL
from workforce_manager.responsable.domaine import FICHIER_DOMAINE, DomaineConnu
from workforce_manager.responsable.superviseur import Proposition, SuperviseurDelegation, SuperviseurFixe

A = {nom: num for num, nom in ACTIONS.items()}
modeles_prets = pytest.mark.skipif(not (FICHIER_PPO_GENERAL.exists() and FICHIER_DOMAINE.exists()),
                                   reason="modèle PPO ou domaine connu absent")


def agent(**kwargs):
    from workforce_manager.responsable.agent import AgentResponsable
    return AgentResponsable(**kwargs)


# --------------------------------------------------------------------------- 1. masquage

def test_masque_identique_a_la_faisabilite_reelle():
    """Pour des états variés, le masque dit exactement ce que l'action fera (sans la jouer)."""
    rng = np.random.default_rng(0)
    for i in range(5):
        env = CallCenterEnv()
        env.reset(seed=i, options={"scenario_def": generer_scenario(10_000_000 + i)})
        for _ in range(48):
            masque = env.action_masks()
            for a in range(len(ACTIONS)):
                assert copy.deepcopy(env)._appliquer_action(a) == masque[a]
            env.step(int(rng.integers(len(ACTIONS))))


@modeles_prets
@pytest.mark.parametrize("scenario", ["journee_normale", "forte_affluence", "sous_effectif"])
def test_agent_responsable_aucune_action_impossible(scenario):
    assert jouer_journee(agent(), scenario, graine=0)["actions_impossibles"] == 0


# --------------------------------------------------------------------------- 2. validation humaine

def proposition(action="heures_supplementaires", cout=3.6, **situation):
    base = {"standard": 0, "sante": 0, "urgence": 0, "prevision": 40, "evenements": []}
    return Proposition("10h00", action, cout, "texte", {**base, **situation})


def test_delegation_refuse_heures_sup_sans_besoin():
    accepte, raison = SuperviseurDelegation().valider(proposition())
    assert not accepte and "aucun client" in raison


def test_delegation_accepte_heures_sup_justifiees():
    assert SuperviseurDelegation().valider(proposition(standard=5))[0]


def test_delegation_respecte_le_budget_journalier():
    sup = SuperviseurDelegation()
    reponses = [sup.valider(proposition("planifier_renfort", 4.0))[0] for _ in range(25)]
    assert reponses.count(True) == 20 and not reponses[-1]          # 20 x 4 = 80 points


@modeles_prets
def test_proposition_refusee_maintient_l_organisation():
    refus = SuperviseurFixe(accepte=False)
    a = agent(superviseur=refus)
    jouer_journee(a, "forte_affluence", graine=0)
    couteuses = {"activer_conseiller_supplementaire", "heures_supplementaires", "planifier_renfort"}
    assert refus.recues                                               # l'agent a bien proposé
    assert all(e["action_executee"] not in couteuses for e in a.journal)
    assert all(e["action_executee"] == "maintenir_organisation"
               for e in a.journal if e["validation"] and not e["validation"]["accepte"])


@modeles_prets
def test_seules_les_actions_couteuses_passent_par_le_superviseur():
    sup = SuperviseurFixe(accepte=True)
    a = agent(superviseur=sup)
    jouer_journee(a, "campagne_commerciale", graine=1)
    assert {p.action for p in sup.recues} <= {"activer_conseiller_supplementaire", "heures_supplementaires",
                                              "planifier_renfort"}


# --------------------------------------------------------------------------- 3. situations inconnues

@modeles_prets
def test_situation_connue_sans_anomalie():
    env = CallCenterEnv("journee_normale")
    obs, _ = env.reset(seed=0)
    assert DomaineConnu.charger().anomalies(obs) == []


@modeles_prets
def test_file_jamais_vue_detectee():
    obs = np.zeros(len(NOMS_ETAT), dtype=np.float32)
    obs[NOMS_ETAT.index("file_urgence")] = 1.0                # 5 urgences en file
    anomalies = DomaineConnu.charger().anomalies(obs)
    assert anomalies and "file_urgence" in anomalies[0]


@modeles_prets
def test_evenements_simultanes_detectes():
    obs = np.zeros(len(NOMS_ETAT), dtype=np.float32)
    for nom in list(FAMILLES_EVENEMENTS)[:2]:
        obs[NOMS_ETAT.index(nom)] = 1.0
    assert any("simultanés" in a for a in DomaineConnu.charger().anomalies(obs))


@modeles_prets
def test_repli_sur_les_regles_pendant_au_moins_une_heure():
    a = agent()
    a.reset()
    inconnue = np.zeros(len(NOMS_ETAT), dtype=np.float32)
    inconnue[NOMS_ETAT.index("file_urgence")] = 1.0
    normale = np.zeros(len(NOMS_ETAT), dtype=np.float32)
    a.agir(inconnue)
    for _ in range(3):
        a.agir(normale)
    a.agir(normale)
    sources = [e["source"] for e in a.journal]
    assert sources[:4] == ["règles (repli : situation inconnue)"] * 4 and sources[4] == "agent PPO"


# --------------------------------------------------------------------------- 4. journal

@modeles_prets
def test_journal_une_entree_par_decision_complete():
    a = agent()
    jouer_journee(a, "sami_rupture_stock", graine=0)
    assert len(a.journal) == 48
    for e in a.journal:
        assert {"heure", "source", "action_proposee", "action_executee", "confiance", "explication",
                "validation", "situation_inconnue", "actions_masquees", "situation"} <= set(e)
        assert e["explication"]
        if e["source"] == "agent PPO":
            assert 0 < e["confiance"] <= 1
    resume = a.resume_journal()
    assert resume["decisions"] == 48 == resume["decisions_agent"] + resume["decisions_repli_regles"]


@modeles_prets
def test_api_simulate_day_renvoie_le_journal():
    from fastapi.testclient import TestClient

    from workforce_manager.api.main import app
    r = TestClient(app).post("/api/agents/workforce-manager/simulate-day",
                             json={"scenario": "sous_effectif", "policy": "responsable"})
    assert r.status_code == 200
    assert len(r.json()["journal"]) == 48 and r.json()["journal_resume"]["decisions"] == 48
