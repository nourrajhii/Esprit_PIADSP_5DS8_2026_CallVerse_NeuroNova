"""Tests de l'état, des actions et de la récompense (version 2, grille d'évaluation).

Lancement : python -m pytest workforce_manager/tests -v
"""

import numpy as np
import pytest

from workforce_manager.env.call_center_env import (
    ACTIONS, DELAI_RENFORT_PAS, FAMILLES_EVENEMENTS, NOMS_ETAT, CallCenterEnv,
)
from workforce_manager.env.reward import COMPOSANTES, charger_poids, penalite_occupation

A = {nom: num for num, nom in ACTIONS.items()}
GRAINES = range(20)


def nouvel_env(scenario: str = "journee_normale", graine: int = 0) -> CallCenterEnv:
    env = CallCenterEnv(scenario=scenario)
    env.reset(seed=graine)
    return env


def jouer(env, nom_action: str) -> dict:
    return env.step(A[nom_action])[4]


# --------------------------------------------------------------------------- grille : état

def test_etat_contient_les_variables_de_la_grille():
    attendues = {"clients_en_attente", "file_standard", "file_sante", "file_urgence",
                 "conseillers_libres_generalistes", "conseillers_libres_sante", "conseillers_occupes",
                 "taux_occupation", "volume_entrant_recent", "taux_abandon_recent", "attente_moyenne",
                 "aht_recent", "fcr_recent", "taux_escalade_recent", "satisfaction_recente",
                 "prevision_charge", *FAMILLES_EVENEMENTS}
    assert attendues <= set(NOMS_ETAT)


def test_etat_normalise_sur_une_journee_aleatoire():
    """Même avec des actions au hasard, l'état reste dans [0, 1] et rien ne plante."""
    env = nouvel_env("forte_affluence", graine=3)
    rng = np.random.default_rng(3)
    termine = False
    while not termine:
        obs, _, termine, _, _ = env.step(int(rng.integers(len(ACTIONS))))
        assert obs.shape == (len(NOMS_ETAT),)
        assert env.observation_space.contains(obs)


@pytest.mark.parametrize("scenario, famille, pas", [
    ("sami_rupture_stock", "evt_stock_sante", 8),          # 10h00
    ("incident_technique", "evt_incident_technique", 24),  # 14h00
    ("campagne_commerciale", "evt_campagne_commerciale", 8),
    ("forte_affluence", "evt_pic_demande", 4),
    ("sous_effectif", "evt_sous_effectif", 0),
])
def test_evenements_visibles_dans_l_etat(scenario, famille, pas):
    env = nouvel_env(scenario)
    for _ in range(pas):
        env.step(0)
    assert env._info()["etat"][famille] == 1.0


def test_prevision_n_annonce_pas_l_imprevu():
    """Rupture de stock imprévue : la prévision de 9h pour 10h est celle d'une journée normale."""
    normale, sami = nouvel_env("journee_normale"), nouvel_env("sami_rupture_stock")
    for env in (normale, sami):
        for _ in range(4):          # 9h00 : on regarde la prévision pour 10h
            env.step(0)
    assert normale._info()["etat"]["prevision_charge"] == sami._info()["etat"]["prevision_charge"]


def test_prevision_annonce_la_campagne_planifiee():
    normale, campagne = nouvel_env("journee_normale"), nouvel_env("campagne_commerciale")
    for env in (normale, campagne):
        for _ in range(4):
            env.step(0)
    assert campagne._info()["etat"]["prevision_charge"] > normale._info()["etat"]["prevision_charge"]


# --------------------------------------------------------------------------- grille : actions

def test_dix_actions_de_la_grille():
    assert len(ACTIONS) == 10 and ACTIONS[0] == "maintenir_organisation"


def test_reserve_epuisee_sans_planter():
    env = nouvel_env()
    possibles = [jouer(env, "activer_conseiller_supplementaire")["action_possible"] for _ in range(4)]
    assert possibles == [True, True, True, False]       # 3 conseillers en réserve seulement
    assert env._info()["recompense_detail"]["action_impossible"] < 0


def test_reduction_limitee_par_le_minimum():
    env = nouvel_env()
    possibles = [jouer(env, "reduire_effectif")["action_possible"] for _ in range(5)]
    assert env._info()["conseillers"]["actifs"] >= 5
    assert False in possibles


def test_reaffectation_dans_les_deux_sens():
    env = nouvel_env()
    info = jouer(env, "affecter_conseiller_file_sante")
    assert info["conseillers"]["dedies_sante"] == 1
    info = jouer(env, "reaffecter_conseiller_file_standard")      # le généraliste revient polyvalent
    assert info["conseillers"]["dedies_sante"] == 0
    info = jouer(env, "reaffecter_conseiller_file_standard")      # un profil santé part au standard
    assert info["conseillers"]["dedies_standard"] == 1


@pytest.mark.parametrize("action, mode", [("modifier_priorites", "mode_priorite"),
                                          ("affecter_selon_competences", "mode_competences")])
def test_modes_de_routage_basculent_et_sont_visibles(action, mode):
    env = nouvel_env()
    assert jouer(env, action)["etat"][mode] == 1.0
    assert jouer(env, action)["etat"][mode] == 0.0


def test_heures_sup_limitees_et_temporaires():
    env = nouvel_env()
    possibles = [jouer(env, "heures_supplementaires")["action_possible"] for _ in range(3)]
    assert possibles == [True, True, False]
    for _ in range(4):
        info = env.step(0)[4]
    assert info["conseillers"]["heures_sup"] == 0        # partis après 1 heure


def test_renfort_planifie_arrive_30_min_plus_tard_sans_majoration():
    env = nouvel_env()
    info = jouer(env, "planifier_renfort")
    assert info["conseillers"]["renforts_planifies"] == 1 and info["conseillers"]["actifs"] == 8
    for _ in range(DELAI_RENFORT_PAS):
        info = env.step(0)[4]
    assert info["conseillers"]["renforts_presents"] == 1 and info["conseillers"]["actifs"] == 9
    assert info["recompense_detail"]["heures_sup"] == 0      # coût normal, pas d'heures sup


def test_formation_indisponible_puis_forme():
    env = nouvel_env()
    info = jouer(env, "formation")
    assert info["action_possible"] and info["conseillers"]["en_formation"] == 1
    env.step(0)
    info = env.step(0)[4]
    assert info["conseillers"]["en_formation"] == 0 and info["conseillers"]["formes"] == 1


# --------------------------------------------------------------------------- grille : scénarios

def test_sous_effectif_retire_trois_conseillers():
    env = nouvel_env("sous_effectif")
    c = env._info()["conseillers"]
    assert c["absents"] == 3 and c["actifs"] == 5


def test_clients_non_resolus_rappellent():
    env = nouvel_env("journee_normale", graine=1)
    termine = False
    while not termine:
        _, _, termine, _, info = env.step(0)
    assert info["rappels_recus"] > 0 and 0.6 < info["fcr"] < 0.95


# --------------------------------------------------------------------------- récompense

def test_heures_sup_file_vide_moins_bien_que_ne_rien_faire():
    """Action absurde : heures sup à 8h00, alors qu'aucun client n'attend."""
    gains_rien, gains_heures_sup = [], []
    for graine in GRAINES:
        env_rien, env_hs = nouvel_env(graine=graine), nouvel_env(graine=graine)
        assert sum(env_hs._info()["files"].values()) == 0          # la file est bien vide
        gains_rien.append(env_rien.step(0)[1])
        _, r_hs, _, _, info = env_hs.step(A["heures_supplementaires"])
        gains_heures_sup.append(r_hs)
        assert info["action_possible"]
        assert info["recompense_detail"]["heures_sup"] < 0          # la composante explique l'écart
    assert np.mean(gains_heures_sup) < np.mean(gains_rien)
    assert sum(h < r for h, r in zip(gains_heures_sup, gains_rien)) >= 18   # au moins 90 % des graines


def test_detail_de_la_recompense_complet_et_coherent():
    env = nouvel_env("sami_rupture_stock")
    for _ in range(12):
        _, recompense, _, _, info = env.step(0)
        detail = info["recompense_detail"]
        assert set(detail) == set(COMPOSANTES) | {"total"}
        assert sum(detail[c] for c in COMPOSANTES) == pytest.approx(detail["total"], abs=1e-3)
        assert recompense == pytest.approx(detail["total"])


def test_composantes_de_la_grille_presentes():
    assert {"resolus", "attente", "abandons", "sla_urgence", "occupation", "satisfaction",
            "cout_conseillers"} <= set(COMPOSANTES)


@pytest.mark.parametrize("occupees, disponibles, attendu", [
    (70, 100, 0.0),      # 70 % : dans la plage raisonnable
    (100, 100, 2.0),     # 100 % : surcharge maximale
    (0, 100, 0.5),       # 0 % : sous-emploi maximal
])
def test_penalite_occupation(occupees, disponibles, attendu):
    stats = {"minutes_occupees": occupees, "minutes_disponibles": disponibles}
    assert penalite_occupation(stats, charger_poids()) == pytest.approx(attendu)


def test_hierarchie_des_poids_metier():
    """Un abandon coûte plus qu'un appel ne rapporte, et urgence > santé > standard."""
    p = charger_poids()
    assert p["abandon"]["urgence"] > p["abandon"]["sante"] > p["abandon"]["standard"]
    for f in ("standard", "sante", "urgence"):
        assert p["abandon"][f] > p["resolu"][f]


def test_renforcer_le_centre_pendant_sami_ameliore_la_recompense():
    """Organiser, prioriser et activer la réserve au début de la rupture doit être récompensé."""
    def journee(graine, plan):
        env = nouvel_env("sami_rupture_stock", graine)
        termine = False
        while not termine:
            _, _, termine, _, info = env.step(plan.get(env.pas, 0))
        return info["recompense_cumul"]["total"]

    renfort = {0: A["affecter_selon_competences"], 8: A["modifier_priorites"],
               9: A["activer_conseiller_supplementaire"], 10: A["activer_conseiller_supplementaire"],
               11: A["activer_conseiller_supplementaire"]}
    gains = [journee(g, renfort) - journee(g, {}) for g in range(5)]
    assert np.mean(gains) > 0
