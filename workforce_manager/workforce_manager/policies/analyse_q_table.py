"""Lit la Q-table apprise et explique, en clair, ce que l'agent a appris.

Lancement (depuis le dossier parent de workforce_manager/) :
    python -m workforce_manager.policies.analyse_q_table
"""

from collections import Counter

import numpy as np
import pandas as pd

from workforce_manager.env.call_center_env import ACTIONS
from workforce_manager.evaluation.run_policy import SCENARIOS, jouer_journee
from workforce_manager.policies.q_learning import (
    BINS_FILE_SANTE, TRANCHES, QLearningPolicy, decrire_etat,
)

# On n'interprète que les cases vues assez souvent : en dessous, la valeur Q est du bruit.
MIN_VISITES = 50
NB_JOURNEES_EVAL = 20


def table_politique(politique: QLearningPolicy) -> pd.DataFrame:
    """Une ligne par case visitée : description, meilleure action, écart avec la 2e."""
    lignes = []
    for etat in range(len(politique.q)):
        visites = int(politique.visites[etat].sum())
        if visites < MIN_VISITES:
            continue
        valeurs = politique.q[etat]
        ordre = np.argsort(valeurs)[::-1]
        lignes.append({
            **decrire_etat(etat), "visites": visites,
            "meilleure_action": ACTIONS[ordre[0]], "Q_meilleure": valeurs[ordre[0]],
            "2e_action": ACTIONS[ordre[1]], "Q_2e": valeurs[ordre[1]],
            "Q_rien": valeurs[0],
        })
    return pd.DataFrame(lignes)


def afficher_lignes(table: pd.DataFrame) -> None:
    print(f"=== Extrait de la Q-table ({len(table)} cases vues >= {MIN_VISITES} fois) ===")
    colonnes = ["tranche", "file_sante", "file_standard", "libres", "visites",
                "meilleure_action", "Q_meilleure", "2e_action", "Q_2e", "Q_rien"]
    extrait = pd.concat([
        table.sort_values("visites", ascending=False).head(8),          # situations courantes
        table[table["file_sante"] == "4+"].head(4),                      # file santé chargée
        table[(table["file_standard"] == "6+") & (table["libres"] == "0")].head(4),   # débordement
    ]).drop_duplicates()
    with pd.option_context("display.width", 200, "display.precision", 1):
        print(extrait[colonnes].to_string(index=False))


def resumer_strategie(table: pd.DataFrame) -> None:
    """Action préférée selon la situation : c'est « ce que l'agent a appris »."""
    print("\n=== Action préférée par tranche horaire (nombre de cases) ===")
    for tranche in TRANCHES:
        compte = Counter(table[table["tranche"] == tranche]["meilleure_action"])
        print(f"  {tranche:11s} {dict(compte.most_common())}")
    print("\n=== Action préférée selon la file santé ===")
    for niveau in BINS_FILE_SANTE:
        compte = Counter(table[table["file_sante"] == niveau]["meilleure_action"])
        print(f"  file santé {niveau:4s} {dict(compte.most_common())}")
    calme = table[(table["file_sante"] == "0") & (table["file_standard"] == "0") & (table["libres"] == "2+")]
    print("\n=== Centre calme (aucune file, 2+ conseillers libres) ===")
    print("  " + ", ".join(f"{r.tranche}: {r.meilleure_action}" for r in calme.itertuples()))


def evaluer(politique: QLearningPolicy) -> None:
    """Politique gloutonne (sans exploration) sur les graines d'évaluation 0..19."""
    print(f"\n=== Politique gloutonne, {NB_JOURNEES_EVAL} journées par scénario (graines d'évaluation) ===")
    for scenario in SCENARIOS:
        kpi = pd.DataFrame([jouer_journee(politique, scenario, g) for g in range(NB_JOURNEES_EVAL)])
        print(f"  {scenario:26s} récompense {kpi['recompense_totale'].mean():7.1f}"
              f" | abandons {kpi['taux_abandon'].mean():5.1%} | SLA urgence {kpi['respect_sla_urgence'].mean():5.1%}"
              f" | actions impossibles {kpi['actions_impossibles'].mean():4.1f}/jour")


def main() -> None:
    politique = QLearningPolicy()
    table = table_politique(politique)
    afficher_lignes(table)
    resumer_strategie(table)
    evaluer(politique)


if __name__ == "__main__":
    main()
