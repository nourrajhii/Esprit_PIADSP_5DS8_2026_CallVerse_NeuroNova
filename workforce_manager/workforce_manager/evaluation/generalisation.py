"""Test de généralisation : l'agent marche-t-il sur n'importe quelle journée ?

Lancement (depuis le dossier parent de workforce_manager/), ~6 min CPU :
    python -m workforce_manager.evaluation.generalisation

Protocole
- 100 journées générées au hasard (graines 900 000+), JAMAIS vues à l'entraînement
  ni en validation : volumes de ~150 à ~1 500 appels, incidents variés.
- Toutes les politiques jouent les mêmes journées (mesures appariées, Wilcoxon + Holm).
- Contrôle : le PPO généraliste reste-t-il bon sur les 4 journées connues (50 journées) ?

Sorties : evaluation/resultats/generalisation.csv, generalisation_stats.csv,
          evaluation/figures/generalisation_volume.png
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from workforce_manager.env.random_scenarios import scenarios_de_test
from workforce_manager.evaluation.compare_policies import (
    ENCRE, ENCRE_2, GRILLE, SURFACE, _style, comparer, correction_holm,
)
from workforce_manager.evaluation.run_policy import NB_JOURNEES, POLITIQUES, SCENARIOS, evaluer, jouer_journee

NB_JOURNEES_TEST = 100
POLITIQUES_TESTEES = ["rien", "regles", "qlearning", "ppo", "ppo_general"]
COMPARAISONS = [("ppo_general", "regles"), ("ppo", "regles"), ("ppo_general", "ppo")]
# Tranches de volume : les 4 journées connues font 470 à 800 appels.
TRANCHES = [0, 400, 800, 10_000]
NOMS_TRANCHES = ["< 400 (plus calme que connu)", "400-800 (comme connu)", "> 800 (plus chargé que connu)"]
COULEURS = {"ppo": "#e87ba4", "ppo_general": "#008300"}
NOMS = {"ppo": "PPO standard", "ppo_general": "PPO généraliste"}

RACINE = Path(__file__).parent
FICHIER_JOURNEES = RACINE / "resultats" / "generalisation.csv"
FICHIER_STATS = RACINE / "resultats" / "generalisation_stats.csv"
FICHIER_FIGURE = RACINE / "figures" / "generalisation_volume.png"


def evaluer_journees_aleatoires(nombre: int = NB_JOURNEES_TEST) -> pd.DataFrame:
    """Une ligne par (politique, journée aléatoire)."""
    lignes = []
    for i, scenario in enumerate(scenarios_de_test(nombre)):
        evenement = scenario["evenements"][0]["type"] if scenario["evenements"] else "aucun"
        for nom in POLITIQUES_TESTEES:
            kpi = jouer_journee(POLITIQUES[nom](), scenario, graine=i)
            lignes.append({"politique": nom, "scenario": "aleatoire", "graine": i, "evenement": evenement,
                           "volume_prevu": sum(scenario["volume_appels_par_heure"]), **kpi})
    return pd.DataFrame(lignes)


def stats_appariees(df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    res = pd.DataFrame([comparer(df, a, b, "aleatoire", kpi, rng)
                        for kpi in ("recompense_totale", "taux_abandon") for a, b in COMPARAISONS])
    res["p_holm"] = correction_holm(res["p_wilcoxon"])
    res["significatif"] = res["p_holm"] < 0.05
    return res


def ecarts_par_tranche(df: pd.DataFrame) -> pd.DataFrame:
    """Écart de récompense avec les règles, par tranche de volume journalier."""
    piv = df.pivot(index="graine", columns="politique", values="recompense_totale")
    volume = df.groupby("graine")["volume_prevu"].first()
    tranche = pd.cut(volume, TRANCHES, labels=NOMS_TRANCHES)
    lignes = []
    for nom in ("ppo", "ppo_general"):
        ecart = piv[nom] - piv["regles"]
        for t, groupe in ecart.groupby(tranche, observed=True):
            lignes.append({"politique": nom, "tranche": t, "journees": len(groupe),
                           "ecart_moyen": groupe.mean(), "pire_ecart": groupe.min(),
                           "jours_meilleur": int((groupe > 0).sum())})
    return pd.DataFrame(lignes)


def figure_volume(df: pd.DataFrame) -> Path:
    """Écart avec les règles selon le volume de la journée : où l'agent échoue-t-il ?"""
    piv = df.pivot(index="graine", columns="politique", values="recompense_totale")
    volume = df.groupby("graine")["volume_prevu"].first()
    fig, ax = plt.subplots(figsize=(9.5, 5), facecolor=SURFACE)
    _style(ax)
    ax.axvspan(470, 800, color=GRILLE, alpha=0.6, linewidth=0)
    ax.text(635, 0.97, "volumes des 4 journées\nd'entraînement", transform=ax.get_xaxis_transform(),
            ha="center", va="top", color=ENCRE_2, fontsize=9)
    ax.axhline(0, color="#898781", linewidth=1)
    for nom in ("ppo", "ppo_general"):
        ax.scatter(volume, piv[nom] - piv["regles"], s=36, color=COULEURS[nom], alpha=0.85,
                   edgecolors=SURFACE, linewidths=1.5, label=NOMS[nom])
    ax.set_xlabel("appels prévus dans la journée", color=ENCRE_2)
    ax.set_ylabel("récompense : PPO − règles (par journée)", color=ENCRE_2)
    ax.set_title("Généralisation sur 100 journées inconnues (au-dessus de 0 = mieux que le chef de plateau)",
                 color=ENCRE, fontsize=11)
    ax.legend(frameon=False, loc="lower left")
    fig.tight_layout()
    FICHIER_FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FICHIER_FIGURE, dpi=130, facecolor=SURFACE)
    plt.close(fig)
    return FICHIER_FIGURE


def controle_journees_connues() -> pd.DataFrame:
    """Le généraliste n'a-t-il rien perdu sur Sami, Inès, Karim et la journée normale ?"""
    df = evaluer(["regles", "ppo", "ppo_general"], SCENARIOS, NB_JOURNEES)
    return df.groupby(["scenario", "politique"])["recompense_totale"].mean().unstack().reindex(SCENARIOS)


def main() -> None:
    df = evaluer_journees_aleatoires()
    FICHIER_JOURNEES.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(FICHIER_JOURNEES, index=False, encoding="utf-8")
    res = stats_appariees(df)
    res.to_csv(FICHIER_STATS, index=False, encoding="utf-8")

    print(f"=== {NB_JOURNEES_TEST} journées inconnues : moyennes ===")
    moyennes = df.groupby("politique")[["recompense_totale", "taux_abandon", "taux_abandon_sante",
                                        "respect_sla_urgence", "cout"]].mean().reindex(POLITIQUES_TESTEES)
    print(moyennes.round(3).to_string())
    print("\n=== Tests appariés (Wilcoxon + Holm) ===")
    for r in res.itertuples():
        print(f"{r.kpi:18s} {r.comparaison:22s} diff {r.difference:+8.3f} IC95 [{r.ic95_bas:+.3f} ; {r.ic95_haut:+.3f}]"
              f"  meilleur {r.a_meilleur_jours:3d}/{NB_JOURNEES_TEST}  p_holm {r.p_holm:.1e}"
              f"  {'SIGNIFICATIF' if r.significatif else 'non significatif'}")
    print("\n=== Écart avec les règles par tranche de volume ===")
    print(ecarts_par_tranche(df).round(1).to_string(index=False))
    print("\n=== Contrôle : journées connues (50 par scénario) ===")
    print(controle_journees_connues().round(1).to_string())
    print(f"\nFigure : {figure_volume(df)}")


if __name__ == "__main__":
    main()
