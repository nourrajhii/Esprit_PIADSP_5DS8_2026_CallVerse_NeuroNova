"""Évalue des politiques sur N journées par scénario (graines fixées) et enregistre les KPI.

Lancement (depuis le dossier parent de workforce_manager/) :
    python -m workforce_manager.evaluation.run_policy
    python -m workforce_manager.evaluation.run_policy --n 10 --politiques aleatoire regles

Sortie : evaluation/resultats/baselines.csv (une ligne par politique x scénario x journée).
"""

import argparse
from pathlib import Path

import pandas as pd

from workforce_manager.env.call_center_env import CallCenterEnv
from workforce_manager.env.scenario_mix import SCENARIOS_ENTRAINEMENT
from workforce_manager.policies.no_action_policy import NoActionPolicy
from workforce_manager.policies.random_policy import RandomPolicy
from workforce_manager.policies.rule_policy import RulePolicy

# Les 8 journées types : 4 personas + les situations de la grille d'évaluation.
SCENARIOS = list(SCENARIOS_ENTRAINEMENT)


def _qlearning():
    """Chargement tardif : nécessite policies/modeles/q_table.npz (train_q_learning)."""
    from workforce_manager.policies.q_learning import QLearningPolicy
    return QLearningPolicy()


def _ppo():
    """Chargement tardif : nécessite policies/modeles/ppo_workforce.zip (train_ppo)."""
    from workforce_manager.policies.ppo import PPOPolicy
    return PPOPolicy()


def _ppo_general():
    """PPO entraîné aussi sur des journées aléatoires (train_ppo --variante generaliste)."""
    from workforce_manager.policies.ppo import FICHIER_PPO_GENERAL, PPOPolicy
    return PPOPolicy(FICHIER_PPO_GENERAL)


def _responsable():
    """PPO généraliste + garde-fous (inconnu, masquage, validation, journal) : responsable/agent.py."""
    from workforce_manager.responsable.agent import AgentResponsable
    return AgentResponsable()


BASELINES = {"rien": NoActionPolicy, "aleatoire": RandomPolicy, "regles": RulePolicy}
POLITIQUES = {**BASELINES, "qlearning": _qlearning, "ppo": _ppo, "ppo_general": _ppo_general,
              "responsable": _responsable}


def choisir_action(politique, observation, env) -> int:
    """Les politiques qui le savent reçoivent le masque des actions possibles."""
    if getattr(politique, "accepte_masque", False):
        return politique.agir(observation, env.action_masks())
    return politique.agir(observation)
NB_JOURNEES = 50
# Les graines de la politique sont décalées : le hasard de la politique aléatoire
# ne doit pas être corrélé au hasard des arrivées d'appels.
DECALAGE_GRAINE_POLITIQUE = 10_000
FICHIER_SORTIE = Path(__file__).parent / "resultats" / "baselines.csv"

# KPI affichés dans le tableau comparatif (moyenne sur les journées).
KPI_TABLEAU = [
    "recompense_totale", "taux_abandon", "taux_abandon_sante", "respect_sla_urgence",
    "attente_moyenne_min", "fcr", "satisfaction", "taux_occupation", "taux_escalade", "cout",
    "heures_sup_h", "actions_impossibles",
]


def jouer_journee(politique, scenario, graine: int) -> dict:
    """Joue une journée complète et renvoie ses KPI.

    scenario : nom d'un scénario de data/scenarios.json, ou définition complète (dict)
    d'une journée générée (env/random_scenarios.py).
    """
    env = CallCenterEnv()
    options = {"scenario_def": scenario} if isinstance(scenario, dict) else {"scenario": scenario}
    observation, info = env.reset(seed=graine, options=options)
    politique.reset(graine + DECALAGE_GRAINE_POLITIQUE)
    termine, actions_impossibles = False, 0
    while not termine:
        observation, _, termine, _, info = env.step(choisir_action(politique, observation, env))
        actions_impossibles += int(not info["action_possible"])
    return calculer_kpi(info, actions_impossibles)


def taux(numerateur: float, denominateur: float, si_vide: float = 0.0) -> float:
    return numerateur / denominateur if denominateur else si_vide


def calculer_kpi(info: dict, actions_impossibles: int) -> dict:
    """Transforme l'info de fin de journée en KPI métier."""
    recus, abandons = info["recus_par_file"], info["abandons_par_file"]
    recompense = info["recompense_cumul"]
    return {
        "recompense_totale": recompense["total"],
        "taux_abandon": info["taux_abandon"],
        "taux_abandon_sante": taux(abandons["sante"], recus["sante"]),
        # Une journée sans urgence respecte le SLA à 100 %.
        "respect_sla_urgence": 1 - taux(info["sla_urgence_rates"], recus["urgence"]),
        "attente_moyenne_min": info["attente_moyenne_min"],
        "qualite_moyenne": info["qualite_moyenne"],
        "fcr": info["fcr"],                                   # résolution au premier contact
        "satisfaction": info["satisfaction_moyenne"],         # sur 5 (abandons = 1/5)
        "taux_occupation": info["taux_occupation"],
        "aht_min": info["duree_traitement_moyenne_min"],      # durée moyenne de traitement
        "rappels": info["rappels_recus"],
        "taux_escalade": taux(info["escalades"], info["traites"]),
        # Coût en points de récompense (conseillers payés + majoration heures sup).
        "cout": -(recompense["cout_conseillers"] + recompense["heures_sup"]),
        "heures_conseillers": info["heures_conseillers"],
        "heures_sup_h": info["heures_sup_h"],
        "appels_recus": info["recus"],
        "actions_impossibles": actions_impossibles,
    }


def evaluer(noms_politiques: list, scenarios: list, nb_journees: int) -> pd.DataFrame:
    """Une ligne par (politique, scénario, journée)."""
    lignes = []
    for nom in noms_politiques:
        politique = POLITIQUES[nom]()
        for scenario in scenarios:
            for graine in range(nb_journees):
                kpi = jouer_journee(politique, scenario, graine)
                lignes.append({"politique": nom, "scenario": scenario, "graine": graine, **kpi})
    return pd.DataFrame(lignes)


def tableau_comparatif(df: pd.DataFrame) -> pd.DataFrame:
    """Moyenne des KPI par scénario et par politique."""
    return df.groupby(["scenario", "politique"], sort=False)[KPI_TABLEAU].mean()


def afficher(df: pd.DataFrame) -> None:
    tableau = tableau_comparatif(df).copy()
    for col in ("taux_abandon", "taux_abandon_sante", "respect_sla_urgence", "fcr", "taux_occupation",
                "taux_escalade"):
        tableau[col] = (tableau[col] * 100).round(1).astype(str) + " %"
    with pd.option_context("display.width", 250, "display.max_columns", None, "display.precision", 1):
        print(tableau)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--politiques", nargs="+", default=list(BASELINES), choices=list(POLITIQUES))
    parser.add_argument("--scenarios", nargs="+", default=SCENARIOS, choices=SCENARIOS)
    parser.add_argument("--n", type=int, default=NB_JOURNEES, help="journées par scénario")
    parser.add_argument("--sortie", type=Path, default=FICHIER_SORTIE)
    args = parser.parse_args()

    df = evaluer(args.politiques, args.scenarios, args.n)
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.sortie, index=False, encoding="utf-8")
    print(f"{len(df)} journées enregistrées dans {args.sortie}\n")
    afficher(df)


if __name__ == "__main__":
    main()
