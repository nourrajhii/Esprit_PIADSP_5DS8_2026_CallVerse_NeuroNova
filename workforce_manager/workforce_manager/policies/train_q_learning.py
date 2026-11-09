"""Entraîne l'agent Q-learning tabulaire sur les 4 scénarios mélangés.

Lancement (depuis le dossier parent de workforce_manager/) :
    python -m workforce_manager.policies.train_q_learning
    python -m workforce_manager.policies.train_q_learning --episodes 6000

Sorties :
    policies/modeles/q_table.npz                    meilleure Q-table (validation) + visites
    evaluation/resultats/q_learning_episodes.csv    récompense de chaque épisode
    evaluation/resultats/q_learning_validation.csv  score glouton en validation
    evaluation/figures/q_learning_courbe.png        courbe d'apprentissage
"""

import argparse
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from workforce_manager.env.call_center_env import CallCenterEnv
from workforce_manager.env.scenario_mix import SCENARIOS_ENTRAINEMENT, ScenarioMixEnv
from workforce_manager.evaluation.validation import valider
from workforce_manager.policies.q_learning import (
    NB_ETATS, QLearningAgent, QLearningPolicy, discretiser,
)

GRAINE = 42
NB_EPISODES = 4000
# alpha = 0,1 : l'environnement est très bruité (arrivées de Poisson, pics aléatoires).
# Un pas d'apprentissage petit fait une moyenne sur ~10 expériences au lieu de
# croire la dernière journée vécue.
ALPHA = 0.1
# gamma = 0,95 : horizon effectif ~ 1 / (1 - 0,95) = 20 pas = 5 heures. Les décisions
# (réserve, priorité, formation) produisent leurs effets sur plusieurs heures, mais
# 0,99 donnerait un horizon (100 pas) plus long que la journée elle-même (48 pas).
GAMMA = 0.95
# Exploration : 100 % au début, décroissance exponentielle jusqu'à 5 % atteints à 80 %
# de l'entraînement ; les 20 % restants servent à stabiliser la politique.
EPSILON_DEBUT, EPSILON_MIN, PART_DECROISSANCE = 1.0, 0.05, 0.8
FENETRE_MOYENNE = 200

# Validation : toutes les 250 journées, on joue la politique GLOUTONNE sur 20 journées
# fixes (evaluation/validation.py) et on garde la meilleure Q-table (« early stopping »).
FREQUENCE_VALIDATION = 250

RACINE = Path(__file__).parent.parent
FICHIER_EPISODES = RACINE / "evaluation" / "resultats" / "q_learning_episodes.csv"
FICHIER_VALIDATION = RACINE / "evaluation" / "resultats" / "q_learning_validation.csv"
FICHIER_COURBE = RACINE / "evaluation" / "figures" / "q_learning_courbe.png"


def epsilon(episode: int, nb_episodes: int) -> float:
    progression = min(episode / (PART_DECROISSANCE * nb_episodes), 1.0)
    return max(EPSILON_MIN, EPSILON_DEBUT * (EPSILON_MIN / EPSILON_DEBUT) ** progression)


def jouer_episode(env, agent: QLearningAgent, eps: float, fn_discretiser) -> tuple:
    """Une journée d'apprentissage ; renvoie (scénario, récompense totale)."""
    observation, info = env.reset()
    etat, termine, total = fn_discretiser(observation), False, 0.0
    while not termine:
        action = agent.choisir(etat, eps)
        observation, recompense, termine, _, _ = env.step(action)
        etat_suivant = fn_discretiser(observation)
        agent.apprendre(etat, action, recompense, etat_suivant, termine)
        etat, total = etat_suivant, total + recompense
    return info["scenario"], total


def entrainer(nb_episodes: int, fn_discretiser=discretiser, nb_etats: int = NB_ETATS,
              classe_env_mix=ScenarioMixEnv, classe_env=CallCenterEnv) -> tuple:
    env = classe_env_mix(graine=GRAINE)
    agent = QLearningAgent(ALPHA, GAMMA, graine=GRAINE, nb_etats=nb_etats)
    episodes, validations = [], []
    meilleure = (-np.inf, agent.q.copy())
    debut = time.time()
    for episode in range(nb_episodes):
        eps = epsilon(episode, nb_episodes)
        scenario, total = jouer_episode(env, agent, eps, fn_discretiser)
        episodes.append({"episode": episode, "scenario": scenario, "recompense": total, "epsilon": eps})
        if (episode + 1) % FREQUENCE_VALIDATION == 0:
            politique = QLearningPolicy(q=agent.q.copy(), visites=agent.visites.copy(), fn_discretiser=fn_discretiser)
            score = valider(politique, classe_env)
            validations.append({"episode": episode, "validation": score})
            if score > meilleure[0]:
                meilleure = (score, agent.q.copy())
            print(f"épisode {episode + 1:5d} | epsilon {eps:.3f}"
                  f" | entraînement (250 dern.) {pd.DataFrame(episodes[-250:])['recompense'].mean():7.1f}"
                  f" | validation gloutonne {score:7.1f} | {time.time() - debut:4.0f} s")
    return agent, meilleure, pd.DataFrame(episodes), pd.DataFrame(validations)


def tracer_courbe(df: pd.DataFrame, validations: pd.DataFrame, chemin: Path = FICHIER_COURBE,
                  titre: str = "Q-learning tabulaire – courbe d'apprentissage") -> None:
    """Moyenne glissante globale + par scénario, validation gloutonne, et epsilon."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 5))
    for scenario in SCENARIOS_ENTRAINEMENT:
        sous = df[df["scenario"] == scenario]
        ax.plot(sous["episode"], sous["recompense"].rolling(FENETRE_MOYENNE // 4, min_periods=1).mean(),
                linewidth=1, alpha=0.5, label=scenario)
    ax.plot(df["episode"], df["recompense"].rolling(FENETRE_MOYENNE, min_periods=1).mean(),
            color="black", linewidth=2.5, label=f"entraînement, tous scénarios (moy. glissante {FENETRE_MOYENNE})")
    ax.plot(validations["episode"], validations["validation"], "o-", color="crimson",
            linewidth=1.5, label="validation gloutonne (sans exploration)")
    ax.set_xlabel("épisode (1 épisode = 1 journée)")
    ax.set_ylabel("récompense totale de la journée")
    ax.set_title(titre)
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right", fontsize=8)
    ax2 = ax.twinx()
    ax2.plot(df["episode"], df["epsilon"], color="grey", linestyle="--", linewidth=1)
    ax2.set_ylabel("epsilon (exploration)", color="grey")
    fig.tight_layout()
    fig.savefig(chemin, dpi=120)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=NB_EPISODES)
    args = parser.parse_args()

    agent, (meilleur_score, meilleure_q), df, validations = entrainer(args.episodes)
    agent.sauvegarder(q=meilleure_q)
    FICHIER_EPISODES.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(FICHIER_EPISODES, index=False)
    validations.to_csv(FICHIER_VALIDATION, index=False)
    tracer_courbe(df, validations)
    debut, fin = df["recompense"].head(500).mean(), df["recompense"].tail(500).mean()
    print(f"\nEntraînement : 500 premiers épisodes {debut:.1f} -> 500 derniers {fin:.1f}")
    print(f"Meilleure validation gloutonne : {meilleur_score:.1f} (Q-table sauvegardée)")
    print(f"Courbe : {FICHIER_COURBE}")


if __name__ == "__main__":
    main()
