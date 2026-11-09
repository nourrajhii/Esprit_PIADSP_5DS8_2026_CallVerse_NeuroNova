"""Validation commune aux agents RL : journées fixes, jamais vues en entraînement.

Graines 50 000+ : distinctes de l'entraînement (100 000+) et de l'évaluation finale (0-49).
Journées aléatoires de validation : graines de génération 800 000+ (le test de
généralisation utilise 900 000+, l'entraînement 10 000 000+).
Sert à garder le meilleur modèle pendant l'entraînement (« early stopping »).
"""

import numpy as np

from workforce_manager.env.call_center_env import CallCenterEnv
from workforce_manager.env.random_scenarios import generer_scenario
from workforce_manager.env.scenario_mix import SCENARIOS_ENTRAINEMENT

JOURNEES_VALIDATION = 5            # par scénario connu -> 20 journées
GRAINE_VALIDATION = 50_000
GRAINE_VALIDATION_ALEATOIRE = 800_000


def _jouer(politique, classe_env, graine: int, options: dict) -> float:
    env = classe_env()
    observation, _ = env.reset(seed=graine, options=options)
    termine, total = False, 0.0
    while not termine:
        observation, recompense, termine, _, _ = env.step(politique.agir(observation))
        total += recompense
    return total


def valider(politique, classe_env=CallCenterEnv, nb_journees: int = JOURNEES_VALIDATION,
            nb_aleatoires: int = 0) -> float:
    """Récompense moyenne (méthode agir) sur les journées de validation connues (+ aléatoires)."""
    totaux = [_jouer(politique, classe_env, GRAINE_VALIDATION + i, {"scenario": scenario})
              for scenario in SCENARIOS_ENTRAINEMENT for i in range(nb_journees)]
    totaux += [_jouer(politique, classe_env, GRAINE_VALIDATION + i,
                      {"scenario_def": generer_scenario(GRAINE_VALIDATION_ALEATOIRE + i)})
               for i in range(nb_aleatoires)]
    return float(np.mean(totaux))
