"""Comparaison statistique des 5 politiques sur les MÊMES journées (rôle : data-scientist).

Lancement (depuis le dossier parent de workforce_manager/), ~4 min CPU :
    python -m workforce_manager.evaluation.compare_policies

Protocole
- 5 politiques x 4 scénarios x 50 journées (graines 0-49, jamais vues à l'entraînement).
- Même graine = mêmes appels, mêmes pics, mêmes clients : les mesures sont APPARIÉES.
- Test de Wilcoxon signé (apparié, sans hypothèse de normalité : les récompenses
  journalières sont asymétriques), IC 95 % de la différence moyenne par bootstrap,
  taille d'effet dz de Cohen, correction de Holm pour les comparaisons multiples.

Sorties : evaluation/resultats/comparaison_journees.csv, comparaison_stats.csv,
          evaluation/figures/comparaison_*.png
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from workforce_manager.env.call_center_env import CallCenterEnv, HEURE_OUVERTURE, MINUTES_PAR_PAS
from workforce_manager.evaluation.run_policy import (
    DECALAGE_GRAINE_POLITIQUE, NB_JOURNEES, POLITIQUES, SCENARIOS, evaluer,
)

GRAINE_BOOTSTRAP = 42
NB_BOOTSTRAP = 10_000
SEUIL_ALPHA = 0.05
ORDRE = ["rien", "aleatoire", "regles", "qlearning", "ppo"]
# Comparaisons qui répondent aux questions du rapport :
# le RL bat-il le chef de plateau ? et PPO fait-il mieux que le tabulaire ?
COMPARAISONS = [("ppo", "regles"), ("qlearning", "regles"), ("ppo", "qlearning")]
# KPI où une valeur plus grande est meilleure (pour compter les journées gagnées).
PLUS_GRAND_EST_MIEUX = {"recompense_totale", "respect_sla_urgence", "fcr", "satisfaction"}
KPI_TESTES = {
    "recompense_totale": "récompense",
    "taux_abandon": "taux d'abandon",
    "taux_abandon_sante": "abandon santé",
    "respect_sla_urgence": "SLA urgence",
    "fcr": "résolution au premier contact",
    "satisfaction": "satisfaction",
    "cout": "coût",
}

RACINE = Path(__file__).parent
FICHIER_JOURNEES = RACINE / "resultats" / "comparaison_journees.csv"
FICHIER_STATS = RACINE / "resultats" / "comparaison_stats.csv"
DOSSIER_FIGURES = RACINE / "figures"

# Palette catégorielle validée (dataviz, scripts/validate_palette.js : PASS, contraste
# WARN -> chaque politique est nommée en clair sur les axes et dans les légendes).
COULEURS = {"rien": "#2a78d6", "aleatoire": "#eb6834", "regles": "#1baf7a",
            "qlearning": "#eda100", "ppo": "#e87ba4"}
NOMS = {"rien": "Rien", "aleatoire": "Aléatoire", "regles": "Règles",
        "qlearning": "Q-learning", "ppo": "PPO"}
NOMS_SCENARIOS = {"journee_normale": "Journée normale", "sami_rupture_stock": "Sami – rupture",
                  "ines_urgence_heure_pointe": "Inès – urgence", "karim_retour_sensible": "Karim – retour",
                  "sous_effectif": "Sous-effectif", "incident_technique": "Incident technique",
                  "campagne_commerciale": "Campagne commerciale", "forte_affluence": "Forte affluence"}
ENCRE, ENCRE_2, GRILLE, SURFACE = "#0b0b0b", "#52514e", "#e1e0d9", "#fcfcfb"


# ------------------------------------------------------------------ statistiques

def ic_bootstrap(differences: np.ndarray, rng: np.random.Generator) -> tuple:
    """IC 95 % de la moyenne des différences (percentiles du bootstrap)."""
    tirages = rng.choice(differences, size=(NB_BOOTSTRAP, len(differences))).mean(axis=1)
    return tuple(np.percentile(tirages, [2.5, 97.5]))


def wilcoxon_p(differences: np.ndarray) -> float:
    """p-valeur bilatérale ; 1 si toutes les différences sont nulles (aucun écart)."""
    if np.allclose(differences, 0):
        return 1.0
    return float(stats.wilcoxon(differences).pvalue)


def comparer(df: pd.DataFrame, a: str, b: str, scenario: str, kpi: str, rng) -> dict:
    """Différence appariée a - b sur un KPI et un scénario."""
    sous = df[df["scenario"] == scenario].pivot(index="graine", columns="politique", values=kpi)
    d = (sous[a] - sous[b]).to_numpy()
    bas, haut = ic_bootstrap(d, rng)
    ecart_type = d.std(ddof=1)
    return {
        "scenario": scenario, "kpi": kpi, "comparaison": f"{a} - {b}",
        "moyenne_a": sous[a].mean(), "moyenne_b": sous[b].mean(), "difference": d.mean(),
        "ic95_bas": bas, "ic95_haut": haut,
        "dz_cohen": d.mean() / ecart_type if ecart_type > 0 else 0.0,
        "a_meilleur_jours": int((d > 0).sum()) if kpi in PLUS_GRAND_EST_MIEUX
        else int((d < 0).sum()),
        "p_wilcoxon": wilcoxon_p(d),
    }


def correction_holm(p: pd.Series) -> pd.Series:
    """Holm-Bonferroni : contrôle le risque de faux positif sur l'ensemble des tests."""
    ordre = p.sort_values().index
    m = len(p)
    ajustees = pd.Series(index=p.index, dtype=float)
    courant = 0.0
    for rang, idx in enumerate(ordre):
        courant = max(courant, min(1.0, (m - rang) * p[idx]))
        ajustees[idx] = courant
    return ajustees


def tableau_stats(df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(GRAINE_BOOTSTRAP)
    lignes = [comparer(df, a, b, sc, kpi, rng)
              for kpi in KPI_TESTES for sc in SCENARIOS for a, b in COMPARAISONS]
    res = pd.DataFrame(lignes)
    res["p_holm"] = correction_holm(res["p_wilcoxon"])
    res["significatif"] = res["p_holm"] < SEUIL_ALPHA
    return res


# ------------------------------------------------------------------ trajectoire (Sami)

def abandons_cumules(nom: str, scenario: str, graine: int) -> list:
    """Abandons cumulés à la fin de chaque quart d'heure d'une journée."""
    politique = POLITIQUES[nom]()
    env = CallCenterEnv(scenario=scenario)
    observation, _ = env.reset(seed=graine)
    politique.reset(graine + DECALAGE_GRAINE_POLITIQUE)
    serie, termine = [], False
    while not termine:
        observation, _, termine, _, info = env.step(politique.agir(observation))
        serie.append(info["abandons"])
    return serie


# ------------------------------------------------------------------ graphiques

def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRILLE, linewidth=0.8)
    ax.set_axisbelow(True)
    for cote in ("top", "right"):
        ax.spines[cote].set_visible(False)
    for cote in ("left", "bottom"):
        ax.spines[cote].set_color("#c3c2b7")
    ax.tick_params(colors=ENCRE_2, labelsize=9)


def figure_recompenses(df: pd.DataFrame) -> Path:
    """Distribution de la récompense journalière : une case par scénario (axes propres)."""
    fig, grille = plt.subplots(2, 4, figsize=(16, 8.6), facecolor=SURFACE)
    axes = grille.ravel()
    rng = np.random.default_rng(0)
    for ax, scenario in zip(axes, SCENARIOS):
        _style(ax)
        donnees = [df[(df.scenario == scenario) & (df.politique == p)]["recompense_totale"] for p in ORDRE]
        boites = ax.boxplot(donnees, widths=0.55, patch_artist=True, showfliers=False,
                            medianprops=dict(color=ENCRE, linewidth=2))
        for boite, p in zip(boites["boxes"], ORDRE):
            boite.set(facecolor=COULEURS[p], alpha=0.35, edgecolor=COULEURS[p], linewidth=1.5)
        for i, (valeurs, p) in enumerate(zip(donnees, ORDRE), start=1):
            ax.scatter(i + rng.uniform(-0.15, 0.15, len(valeurs)), valeurs, s=10,
                       color=COULEURS[p], alpha=0.7, linewidths=0)
        ax.set_xticks(range(1, len(ORDRE) + 1), [NOMS[p] for p in ORDRE], rotation=30)
        ax.set_title(NOMS_SCENARIOS[scenario], color=ENCRE, fontsize=11)
    for ax in grille[:, 0]:
        ax.set_ylabel("récompense totale de la journée", color=ENCRE_2)
    fig.suptitle("Récompense journalière par politique (50 journées par scénario, mêmes graines)",
                 color=ENCRE, fontsize=12)
    fig.tight_layout()
    return _sauver(fig, "comparaison_recompenses.png")


def figure_differences(res: pd.DataFrame) -> Path:
    """Forest plot : différence de récompense et IC 95 %, par scénario et comparaison."""
    sous = res[res.kpi == "recompense_totale"]
    hauteur = 1.6 + 0.32 * len(SCENARIOS) * len(COMPARAISONS)     # ~0,3 pouce par ligne
    fig, ax = plt.subplots(figsize=(9.5, hauteur), facecolor=SURFACE)
    _style(ax)
    ax.grid(axis="x", color=GRILLE, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    etiquettes, y = [], 0
    for scenario in SCENARIOS:
        for a, b in COMPARAISONS:
            ligne = sous[(sous.scenario == scenario) & (sous.comparaison == f"{a} - {b}")].iloc[0]
            ax.plot([ligne.ic95_bas, ligne.ic95_haut], [y, y], color=COULEURS[a], linewidth=2)
            ax.scatter(ligne.difference, y, s=64, color=COULEURS[a], zorder=3,
                       edgecolors=SURFACE, linewidths=2)
            marque = " *" if ligne.significatif else ""
            etiquettes.append(f"{NOMS_SCENARIOS[scenario]} · {NOMS[a]} − {NOMS[b]}{marque}")
            y += 1
        y += 0.6
    positions = [i + 0.6 * (i // len(COMPARAISONS)) for i in range(len(etiquettes))]
    ax.set_yticks(positions, etiquettes, fontsize=9)
    ax.invert_yaxis()
    ax.axvline(0, color="#898781", linewidth=1)
    ax.set_xlabel("différence moyenne de récompense par journée (IC 95 % bootstrap)", color=ENCRE_2)
    ax.set_title("Le RL fait-il mieux que le chef de plateau ?  (* = significatif après Holm)",
                 color=ENCRE, fontsize=11)
    fig.tight_layout()
    return _sauver(fig, "comparaison_differences.png")


def figure_trajectoire_sami(trajectoires: dict) -> Path:
    """Abandons cumulés au fil de la journée Sami (moyenne sur 50 journées)."""
    fig, ax = plt.subplots(figsize=(9, 4.8), facecolor=SURFACE)
    _style(ax)
    heures = HEURE_OUVERTURE + (np.arange(1, 49) * MINUTES_PAR_PAS) / 60
    ax.axvspan(10, 14, color=GRILLE, alpha=0.6, linewidth=0)
    ax.text(12, 0.97, "rupture de stock", transform=ax.get_xaxis_transform(), ha="center",
            va="top", color=ENCRE_2, fontsize=9)
    for nom, series in trajectoires.items():
        moyenne = np.mean(series, axis=0)
        ax.plot(heures, moyenne, color=COULEURS[nom], linewidth=2)
        ax.text(heures[-1] + 0.1, moyenne[-1], f"{NOMS[nom]} ({moyenne[-1]:.0f})", color=ENCRE,
                fontsize=9, va="center")
    ax.set_xlim(HEURE_OUVERTURE, 21.6)
    ax.set_xticks(range(8, 21, 2), [f"{h}h" for h in range(8, 21, 2)])
    ax.set_ylabel("appels abandonnés (cumul)", color=ENCRE_2)
    ax.set_title("Scénario Sami : abandons cumulés au fil de la journée (moyenne de 50 journées)",
                 color=ENCRE, fontsize=11)
    fig.tight_layout()
    return _sauver(fig, "comparaison_sami_abandons.png")


def _sauver(fig, nom: str) -> Path:
    DOSSIER_FIGURES.mkdir(parents=True, exist_ok=True)
    chemin = DOSSIER_FIGURES / nom
    fig.savefig(chemin, dpi=130, facecolor=SURFACE)
    plt.close(fig)
    return chemin


# ------------------------------------------------------------------ affichage

def afficher(df: pd.DataFrame, res: pd.DataFrame) -> None:
    moyennes = df.groupby(["scenario", "politique"])[list(KPI_TESTES)].mean().unstack("politique")
    print("=== Récompense moyenne par journée (50 journées) ===")
    print(moyennes["recompense_totale"][ORDRE].reindex(SCENARIOS).round(1).to_string())
    print("\n=== Taux d'abandon moyen ===")
    print((moyennes["taux_abandon"][ORDRE].reindex(SCENARIOS) * 100).round(1).astype(str).add(" %").to_string())
    print("\n=== Tests appariés sur la récompense (Wilcoxon + Holm) ===")
    sous = res[res.kpi == "recompense_totale"]
    for r in sous.itertuples():
        print(f"{NOMS_SCENARIOS[r.scenario]:16s} {r.comparaison:18s} diff {r.difference:+7.1f}"
              f"  IC95 [{r.ic95_bas:+6.1f} ; {r.ic95_haut:+6.1f}]  dz {r.dz_cohen:+5.2f}"
              f"  meilleur {r.a_meilleur_jours:2d}/50 j  p_holm {r.p_holm:.1e}"
              f"  {'SIGNIFICATIF' if r.significatif else 'non significatif'}")


def main() -> None:
    df = evaluer(ORDRE, SCENARIOS, NB_JOURNEES)
    FICHIER_JOURNEES.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(FICHIER_JOURNEES, index=False, encoding="utf-8")
    res = tableau_stats(df)
    res.to_csv(FICHIER_STATS, index=False, encoding="utf-8")
    afficher(df, res)

    trajectoires = {p: [abandons_cumules(p, "sami_rupture_stock", g) for g in range(NB_JOURNEES)]
                    for p in ["rien", "regles", "qlearning", "ppo"]}
    figures = [figure_recompenses(df), figure_differences(res), figure_trajectoire_sami(trajectoires)]
    print("\nFigures :", *figures, sep="\n  ")


if __name__ == "__main__":
    main()
