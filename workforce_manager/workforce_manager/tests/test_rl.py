"""Tests de l'étape 5 : discrétisation, mise à jour Q-learning, environnement mélangé, PPO.

Lancement : python -m pytest workforce_manager/tests -v
"""

import numpy as np
import pytest

from workforce_manager.env.call_center_env import NOMS_ETAT, CallCenterEnv
from workforce_manager.env.scenario_mix import SCENARIOS_ENTRAINEMENT, ScenarioMixEnv
from workforce_manager.policies.ppo import FICHIER_PPO
from workforce_manager.policies.q_learning import (
    NB_ETATS, QLearningAgent, QLearningPolicy, decrire_etat, discretiser,
)
from workforce_manager.policies.train_q_learning import entrainer, epsilon


def observation(**valeurs) -> np.ndarray:
    obs = np.zeros(len(NOMS_ETAT), dtype=np.float32)
    for nom, v in valeurs.items():
        obs[NOMS_ETAT.index(nom)] = v
    return obs


def test_discretisation_bornes():
    # 4 appels santé (4/30), 6 standard (6/30), 1 généraliste libre (1/9), 15h (pas 28/48)
    obs = observation(file_sante=4 / 30, file_standard=6 / 30,
                      conseillers_libres_generalistes=1 / 9, tranche_horaire=28 / 48)
    assert decrire_etat(discretiser(obs)) == {
        "file_sante": "4+", "file_standard": "6+", "libres": "1", "tranche": "apres-midi"}


def test_toutes_les_cases_sont_distinctes():
    assert len({tuple(decrire_etat(i).values()) for i in range(NB_ETATS)}) == NB_ETATS == 108


def test_mise_a_jour_q_learning():
    agent = QLearningAgent(alpha=0.5, gamma=0.9)
    agent.q[1] = 0
    agent.q[1, 1] = 10
    agent.apprendre(etat=0, action=2, recompense=4.0, etat_suivant=1, termine=False)
    assert agent.q[0, 2] == pytest.approx(0.5 * (4 + 0.9 * 10))       # 6,5
    agent.apprendre(etat=0, action=3, recompense=4.0, etat_suivant=1, termine=True)
    assert agent.q[0, 3] == pytest.approx(0.5 * 4)                      # pas de futur en fin de journée


def test_epsilon_decroit_jusqu_au_minimum():
    valeurs = [epsilon(e, 1000) for e in range(1000)]
    assert valeurs[0] == 1.0 and valeurs[-1] == pytest.approx(0.05)
    assert all(a >= b for a, b in zip(valeurs, valeurs[1:]))


def test_case_jamais_vue_donne_rien():
    politique = QLearningPolicy(q=np.ones((NB_ETATS, 7)), visites=np.zeros((NB_ETATS, 7)))
    assert politique.agir(observation()) == 0


def test_scenarios_et_journees_varient():
    env = ScenarioMixEnv(graine=0)
    infos = [env.reset()[1]["scenario"] for _ in range(120)]
    assert set(infos) == set(SCENARIOS_ENTRAINEMENT)
    a = env.reset()[0]
    env.step(0)
    assert env.prochaine_graine >= 100_000


def test_aucune_graine_d_evaluation_a_l_entrainement(monkeypatch):
    """Même si SB3 impose reset(seed=42), la journée jouée n'est pas une journée d'évaluation."""
    graines, original = [], CallCenterEnv.reset

    def espion(self, *, seed=None, options=None):
        graines.append(seed)
        return original(self, seed=seed, options=options)

    monkeypatch.setattr(CallCenterEnv, "reset", espion)
    env = ScenarioMixEnv(graine=0)
    env.reset(seed=42)
    env.reset()
    assert len(graines) == 2 and all(g >= 100_000 for g in graines)


def test_entrainement_court_sans_erreur():
    agent, (score, q), df, _ = entrainer(5)
    assert len(df) == 5 and agent.visites.sum() == 5 * 48


@pytest.mark.skipif(not FICHIER_PPO.exists(), reason="modèle PPO non entraîné")
def test_ppo_charge_et_agit():
    from workforce_manager.policies.ppo import PPOPolicy
    assert 0 <= PPOPolicy().agir(observation()) < 7
