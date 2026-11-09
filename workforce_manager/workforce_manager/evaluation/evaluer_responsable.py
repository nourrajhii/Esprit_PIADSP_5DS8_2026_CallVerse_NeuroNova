"""Effet de la couche « agent responsable » : performance ET activité de chaque garde-fou.

Lancement (depuis le dossier parent de workforce_manager/), ~15 min CPU :
    python -m workforce_manager.evaluation.evaluer_responsable

Compare l'agent responsable, le PPO brut (sans garde-fous) et les règles sur :
1. les 8 journées types (50 journées chacune) ;
2. 100 journées jamais vues (générateur aléatoire) ;
3. 6 cas extrêmes hors de l'entraînement (cumul d'incidents, volume x3, journée vide...).
Sortie : evaluation/resultats/responsable.csv
"""

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd

from workforce_manager.env.random_scenarios import scenarios_de_test
from workforce_manager.evaluation.compare_policies import comparer, correction_holm
from workforce_manager.evaluation.run_policy import (
    DECALAGE_GRAINE_POLITIQUE, POLITIQUES, SCENARIOS, calculer_kpi, choisir_action,
)
from workforce_manager.env.call_center_env import CallCenterEnv

RACINE = Path(__file__).parent.parent
FICHIER = RACINE / "evaluation" / "resultats" / "responsable.csv"
POLITIQUES_COMPAREES = ["regles", "ppo_general", "responsable"]
NB_JOURNEES, NB_INCONNUES, NB_EXTREMES = 50, 100, 10


def cas_extremes() -> dict:
    """Journées construites à partir de la journée normale, hors de tout ce qui a été entraîné."""
    base = {s["id"]: s for s in json.loads((RACINE / "data" / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]}
    normale, volumes = base["journee_normale"], base["journee_normale"]["volume_appels_par_heure"]

    def variante(nom, **modifs):
        s = copy.deepcopy(normale)
        s.update(id=nom, evenements=modifs.pop("evenements", []), **modifs)
        return s

    absence = lambda g, s: {"type": "sous_effectif", "heure_debut": 8, "heure_fin": 20,
                            "effets": {"absents_generalistes": g, "absents_sante": s}}
    return {
        "extreme_cumul_incidents": variante(
            "extreme_cumul_incidents", volume_appels_par_heure=[32, 44, 90, 102, 96, 77, 114, 90, 60, 52, 40, 28],
            volume_prevu_par_heure=volumes, evenements=[
                absence(2, 1),
                {"type": "rupture_stock", "heure_debut": 10, "heure_fin": 14, "effets": {"part_sante": 0.5}},
                {"type": "incident_technique", "heure_debut": 14, "heure_fin": 16, "effets": {"part_sante": 0.15}}]),
        "extreme_volume_x3": variante("extreme_volume_x3", volume_appels_par_heure=[v * 3 for v in volumes],
                                      volume_prevu_par_heure=volumes),
        "extreme_journee_vide": variante("extreme_journee_vide", volume_appels_par_heure=[5] * 12),
        "extreme_urgences_20pct": variante("extreme_urgences_20pct",
                                           part_demandes={"standard": 0.5, "sante": 0.3, "urgence": 0.2}),
        "extreme_5_absents": variante("extreme_5_absents", evenements=[absence(4, 1)]),
        "extreme_prevision_fausse": variante("extreme_prevision_fausse",
                                             volume_prevu_par_heure=[v * 2 for v in volumes]),
    }


def jouer(nom_politique: str, scenario, graine: int) -> dict:
    """Une journée ; pour l'agent responsable, on garde aussi le résumé de son journal."""
    politique = POLITIQUES[nom_politique]()
    env = CallCenterEnv()
    options = {"scenario_def": scenario} if isinstance(scenario, dict) else {"scenario": scenario}
    observation, info = env.reset(seed=graine, options=options)
    politique.reset(graine + DECALAGE_GRAINE_POLITIQUE)
    termine, impossibles = False, 0
    while not termine:
        observation, _, termine, _, info = env.step(choisir_action(politique, observation, env))
        impossibles += int(not info["action_possible"])
    kpi = calculer_kpi(info, impossibles)
    if hasattr(politique, "resume_journal"):
        kpi.update(politique.resume_journal())
    return kpi


def evaluer() -> pd.DataFrame:
    lignes = []
    jeux = [("types", sc, sc, g) for sc in SCENARIOS for g in range(NB_JOURNEES)]
    jeux += [("inconnues", "aleatoire", s, i) for i, s in enumerate(scenarios_de_test(NB_INCONNUES))]
    jeux += [("extremes", nom, s, g) for nom, s in cas_extremes().items() for g in range(NB_EXTREMES)]
    for famille, nom, scenario, graine in jeux:
        for politique in POLITIQUES_COMPAREES:
            lignes.append({"famille": famille, "scenario": nom, "graine": graine, "politique": politique,
                           **jouer(politique, scenario, graine)})
    return pd.DataFrame(lignes)


def afficher(df: pd.DataFrame) -> None:
    rng = np.random.default_rng(42)
    print("=== Récompense moyenne et taux d'abandon ===")
    t = df.groupby(["famille", "scenario", "politique"], sort=False).agg(
        recompense=("recompense_totale", "mean"), abandons=("taux_abandon", "mean"),
        impossibles=("actions_impossibles", "mean")).unstack("politique")
    with pd.option_context("display.width", 220, "display.precision", 3):
        print(t)
    print("\n=== Tests appariés : agent responsable - règles, et responsable - PPO brut ===")
    res = []
    for (famille, sc), sous in df.groupby(["famille", "scenario"], sort=False):
        for b in ("regles", "ppo_general"):
            r = comparer(sous, "responsable", b, sc, "recompense_totale", rng)
            res.append({"famille": famille, **r})
    res = pd.DataFrame(res)
    res["p_holm"] = correction_holm(res["p_wilcoxon"])
    for r in res.itertuples():
        n = len(df[(df.scenario == r.scenario) & (df.politique == "responsable")])
        print(f"{r.famille:9s} {r.scenario:26s} {r.comparaison:28s} diff {r.difference:+7.1f}"
              f"  meilleur {r.a_meilleur_jours:3d}/{n}  p_holm {r.p_holm:.0e}  {'*' if r.p_holm < 0.05 else ''}")
    print("\n=== Activité des garde-fous (moyenne par journée, agent responsable) ===")
    g = df[df.politique == "responsable"].groupby("famille")[
        ["decisions_repli_regles", "propositions_couteuses", "propositions_refusees", "decisions_peu_sures",
         "actions_impossibles"]].mean()
    print(g.round(1).to_string())
    print("\nCas extrêmes avec repli sur les règles :")
    print(df[(df.politique == "responsable") & (df.famille == "extremes")]
          .groupby("scenario")["decisions_repli_regles"].mean().round(1).to_string())


def main() -> None:
    df = evaluer()
    FICHIER.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(FICHIER, index=False, encoding="utf-8")
    afficher(df)


if __name__ == "__main__":
    main()
