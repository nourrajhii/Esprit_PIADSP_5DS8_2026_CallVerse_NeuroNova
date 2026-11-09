"""Tests du générateur de journées aléatoires et de son usage à l'entraînement.

Lancement : python -m pytest workforce_manager/tests -v
"""

import numpy as np
import pytest

from workforce_manager.env.call_center_env import CallCenterEnv
from workforce_manager.env.random_scenarios import (
    GRAINE_ENTRAINEMENT, GRAINE_TEST, PROFILS, TYPES_EVENEMENTS, generer_scenario, scenarios_de_test,
)
from workforce_manager.env.scenario_mix import SCENARIOS_ENTRAINEMENT, ScenarioMixEnv
from workforce_manager.evaluation.run_policy import jouer_journee
from workforce_manager.policies.rule_policy import RulePolicy

ECHANTILLON = [generer_scenario(GRAINE_ENTRAINEMENT + i) for i in range(300)]


@pytest.mark.parametrize("scenario", ECHANTILLON[:50])
def test_scenario_bien_forme(scenario):
    assert len(scenario["volume_appels_par_heure"]) == 12
    assert all(v > 0 for v in scenario["volume_appels_par_heure"])
    assert sum(scenario["part_demandes"].values()) == pytest.approx(1.0, abs=1e-3)
    assert set(scenario["repartition_profils"]) == set(PROFILS)
    assert sum(scenario["repartition_profils"].values()) == pytest.approx(1.0)
    for evt in scenario["evenements"]:
        assert 9 <= evt["heure_debut"] < evt["heure_fin"] <= 20


def test_reproductible():
    assert generer_scenario(123) == generer_scenario(123)
    assert generer_scenario(123) != generer_scenario(124)


def test_couvre_journees_calmes_et_crises():
    """Le but : sortir de la plage 470-800 appels des 4 scénarios connus, des deux côtés."""
    volumes = np.array([sum(s["volume_appels_par_heure"]) for s in ECHANTILLON])
    assert (volumes < 400).mean() > 0.15 and (volumes > 800).mean() > 0.15
    types = {s["evenements"][0]["type"] for s in ECHANTILLON if s["evenements"]}
    assert types == set(TYPES_EVENEMENTS)


def test_journee_generee_jouable_jusqu_au_bout():
    kpi = jouer_journee(RulePolicy(), scenarios_de_test(1)[0], graine=0)
    assert kpi["appels_recus"] > 0 and 0 <= kpi["taux_abandon"] <= 1


def test_env_accepte_une_definition_a_la_volee():
    env = CallCenterEnv()
    _, info = env.reset(seed=0, options={"scenario_def": generer_scenario(5)})
    assert info["scenario"] == "aleatoire"


def test_melange_entrainement_et_test_disjoints():
    """L'entraînement ne tire jamais une journée du jeu de test."""
    env = ScenarioMixEnv(graine=0, part_aleatoire=1.0)
    graines = set()
    for _ in range(50):
        env.reset()
        graines.add(env.scenario["graine_generation"])
    assert all(g >= GRAINE_ENTRAINEMENT for g in graines)
    assert not graines & set(range(GRAINE_TEST, GRAINE_TEST + 1000))


def test_part_aleatoire_respectee():
    env = ScenarioMixEnv(graine=1, part_aleatoire=0.5)
    noms = [env.reset()[1]["scenario"] for _ in range(400)]
    assert 0.4 < noms.count("aleatoire") / 400 < 0.6


def test_sans_aleatoire_suite_inchangee():
    """part_aleatoire=0 : même suite de scénarios qu'avant l'ajout du générateur."""
    rng = np.random.default_rng(7)
    attendus = [str(rng.choice(list(SCENARIOS_ENTRAINEMENT))) for _ in range(20)]
    env = ScenarioMixEnv(graine=7)
    assert [env.reset()[1]["scenario"] for _ in range(20)] == attendus
