"""Démo en direct : Sami, Inès et Karim, pas à pas.

Lancement (depuis le dossier parent de workforce_manager/) :
    python -m workforce_manager.demo                         # les 3 personas
    python -m workforce_manager.demo --persona sami --pause 1
    python -m workforce_manager.demo --sans-llm              # aucun appel Gemini (quota)
    python -m workforce_manager.demo --persona ines --detail  # chaque quart d'heure
    python -m workforce_manager.demo --persona sami --superviseur  # vous validez les 4 premières actions coûteuses

Pour chaque persona, deux niveaux :
- MACRO : la journée est jouée par l'agent PPO ET par les règles du chef de plateau,
  sur la même journée (même graine). À chaque décision de l'agent : situation du centre
  -> décision -> lecture de la situation -> effet sur les 15 min suivantes (vs règles).
- MICRO : au moment de l'appel du persona, sa conversation est évaluée -> décision des
  règles -> explication rédigée par le LLM (1 seul appel Gemini par persona).
Enfin, un avant / après chiffré (règles vs PPO) sur plusieurs journées.

Les textes « lecture de la situation » sont des gabarits (pas le LLM) : PPO est un
réseau de neurones, ces textes décrivent la situation au moment du choix, ils ne
prétendent pas lire dans le réseau.
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from workforce_manager.api.simulation import creer_politique
from workforce_manager.env.call_center_env import ACTIONS, CallCenterEnv
from workforce_manager.evaluation.run_policy import DECALAGE_GRAINE_POLITIQUE, choisir_action, jouer_journee
from workforce_manager.llm.explainer import expliquer
from workforce_manager.micro.quality_rules import decide
from workforce_manager.policies.rule_policy import RulePolicy
from workforce_manager.responsable.agent import AgentResponsable
from workforce_manager.responsable.explication import lecture_situation, lire_etat, situation
from workforce_manager.responsable.superviseur import SuperviseurConsole
from workforce_manager.schemas import QualityEvaluation

RACINE = Path(__file__).parent
FICHIER_AVANT_APRES = RACINE / "evaluation" / "resultats" / "demo_avant_apres.csv"
FICHIER_JOURNAL = RACINE / "evaluation" / "resultats" / "journaux" / "journal.json"
# Journée montrée en direct : la journée MÉDIANE de chaque persona (écart agent - règles le plus
# proche de l'écart médian sur 50 journées) : une journée typique, ni la meilleure ni la pire.
GRAINE_DEMO = 0
NB_JOURNEES_AVANT_APRES = 20
LARGEUR = 92
MAINTENIR = ACTIONS[0]          # "maintenir_organisation" : aucune décision

PERSONAS = {
    "sami": {
        "scenario": "sami_rupture_stock", "heure_appel": "10h30", "profil": "fidele", "graine": 30,
        "presentation": "Sami, abonné diabétique : ses capteurs de glycémie sont en rupture de stock.",
    },
    "ines": {
        "scenario": "ines_urgence_heure_pointe", "heure_appel": "18h15", "profil": "nerveux", "graine": 27,
        "presentation": "Inès appelle en pleine heure de pointe : urgence pour son enfant.",
    },
    "karim": {
        "scenario": "karim_retour_sensible", "heure_appel": "14h30", "profil": "mecontent", "graine": 45,
        "presentation": "Karim veut retourner un tensiomètre défectueux (dispositif médical).",
    },
}


# ------------------------------------------------------------------ affichage

def titre(texte: str, car: str = "=") -> None:
    print("\n" + car * LARGEUR + f"\n{texte}\n" + car * LARGEUR)


# ------------------------------------------------------------------ niveau macro

def effet(info_ppo: dict, info_regles: dict) -> str:
    """Abandons CUMULÉS depuis 8h : plus parlant (et moins bruité) qu'un seul quart d'heure."""
    return (f"clients ayant raccroché depuis 8h -> agent {info_ppo['abandons']} | "
            f"règles {info_regles['abandons']}")


def ligne_decision(entree: dict) -> str:
    """Une décision du journal : action, explication, confiance, garde-fous."""
    confiance = f" [confiance {entree['confiance']:.0%}]" if entree["confiance"] is not None else ""
    return f"{entree['action_executee']}{confiance} : {entree['explication']}"


def garde_fous(entree: dict) -> list:
    """Ce que la couche responsable a fait sur cette décision (refus, repli, faible confiance)."""
    notes = []
    if entree["situation_inconnue"]:
        notes.append("SITUATION INCONNUE -> repli sur les règles : " + "; ".join(entree["situation_inconnue"]))
    v = entree["validation"]
    if v and not v["accepte"]:
        notes.append(f"PROPOSITION REFUSÉE ({entree['action_proposee']}) par {v['par']} : {v['raison']}")
    if entree["peu_sur"] and entree["action_executee"] != MAINTENIR:
        notes.append(f"décision peu sûre ({entree['confiance']:.0%}) : à surveiller")
    return notes


def afficher_pas(heure: str, etat: dict, entree: dict, info_ppo: dict, info_regles: dict) -> None:
    """Mode --detail : chaque décision, quart d'heure par quart d'heure."""
    print(f"\n  SITUATION : {situation(heure, etat)}")
    print(f"  DÉCISION  : {ligne_decision(entree)}  (par : {entree['source']})")
    for note in garde_fous(entree):
        print(f"  GARDE-FOU : {note}")
    print(f"  EFFET     : {effet(info_ppo, info_regles)}")


def afficher_heure(bloc: list, info_ppo: dict, info_regles: dict) -> None:
    """Mode par défaut : un bloc par heure (situation au début, décisions, garde-fous, effet cumulé)."""
    heure, etat = bloc[0]["heure"], bloc[0]["etat"]
    entrees = [p["entree"] for p in bloc]
    decisions = [e for e in entrees if e["action_executee"] != MAINTENIR]
    print(f"\n  {situation(heure, etat)}")
    if not decisions:
        print("    Décisions : aucune, l'agent maintient l'organisation")
    for e in {e["action_executee"]: e for e in decisions}.values():     # une ligne par type d'action
        print(f"    Décision  : {ligne_decision(e)}")
    for note in dict.fromkeys(n for e in entrees for n in garde_fous(e)):
        print(f"    Garde-fou : {note}")
    print(f"    Effet     : {effet(info_ppo, info_regles)}")


def jouer_macro(persona: dict, pause: float, appel_micro, detail: bool = False, superviseur=None,
                graine_imposee=None) -> dict:
    """Joue la journée avec l'agent responsable ET avec les règles (même graine)."""
    scenario = persona["scenario"]
    env_ppo, env_regles = CallCenterEnv(), CallCenterEnv()
    options = {"scenario_def": scenario} if isinstance(scenario, dict) else {"scenario": scenario}
    graine = persona.get("graine", GRAINE_DEMO) if graine_imposee is None else graine_imposee
    obs_ppo, _ = env_ppo.reset(seed=graine, options=options)
    obs_regles, _ = env_regles.reset(seed=graine, options=options)
    agent = AgentResponsable(superviseur=superviseur) if superviseur else creer_politique("responsable")
    regles = RulePolicy()
    for p in (agent, regles):
        p.reset(graine + DECALAGE_GRAINE_POLITIQUE)

    termine, bloc, appel_fait = False, [], False
    while not termine:
        etat, heure = lire_etat(obs_ppo), env_ppo._heure_texte()
        action = choisir_action(agent, obs_ppo, env_ppo)
        entree = agent.journal[-1]
        obs_ppo, _, termine, _, info_ppo = env_ppo.step(action)
        obs_regles, _, _, _, info_regles = env_regles.step(regles.agir(obs_regles))

        bloc.append({"heure": heure, "etat": etat, "entree": entree})
        if detail and (ACTIONS[action] != MAINTENIR or garde_fous(entree)):
            afficher_pas(heure, etat, entree, info_ppo, info_regles)
            time.sleep(pause)
        if len(bloc) == 4:                        # 4 quarts d'heure = 1 heure
            if not detail:
                afficher_heure(bloc, info_ppo, info_regles)
                time.sleep(pause)
            bloc = []
            if not appel_fait and persona["heure_appel"] and info_ppo["heure"] > persona["heure_appel"]:
                appel_micro(info_ppo)
                appel_fait = True
                time.sleep(pause)

    return {"resume": agent.resume_journal(), "journal": agent.journal, "ppo": info_ppo, "regles": info_regles}


# ------------------------------------------------------------------ niveau micro

def charger_evaluation(nom: str) -> tuple:
    brut = json.loads((RACINE / "api" / "exemples" / f"{nom}.json").read_text(encoding="utf-8"))
    return QualityEvaluation.model_validate(brut["evaluation"]), brut["type_demande"]


def scenario_crise() -> dict:
    """Situation JAMAIS VUE à l'entraînement : 3 événements en même temps sur une seule journée."""
    from workforce_manager.evaluation.evaluer_responsable import cas_extremes
    return {"scenario": cas_extremes()["extreme_cumul_incidents"], "heure_appel": None, "profil": None,
            "graine": 0, "presentation": "CRISE jamais vue : 3 absents + rupture de stock (10h) + panne du site (14h)."}


def appel_persona(nom: str, persona: dict, sans_llm: bool):
    """Renvoie la fonction affichée au moment de l'appel du persona (pendant la journée)."""
    def _afficher(info: dict) -> None:
        evaluation, type_demande = charger_evaluation(nom)
        titre(f"  {persona['heure_appel']} - APPEL DE {nom.upper()} ({type_demande}) : sa conversation est évaluée", "-")
        c = evaluation.criteria
        print(f"  ÉVALUATION QUALITÉ : score {evaluation.globalScore}/100 | pertinence {c.pertinence}, "
              f"exactitude {c.exactitude}, groundedness {c.groundedness}, empathie {c.empathie}, "
              f"conformité {c.conformite}")
        decision = decide(evaluation, type_demande)
        contexte = {"heure": persona["heure_appel"], "appels_en_attente_file_sante": info["files"]["sante"],
                    "evenement": persona["presentation"].split(" : ")[-1]}
        if sans_llm:
            source, redigee = "textes fixes (--sans-llm)", decision
        else:
            resultat = expliquer(decision, evaluation, type_demande, persona["profil"], contexte)
            libelles = {"llm": "rédigé par Gemini", "fallback": "textes fixes (LLM indisponible)"}
            source, redigee = libelles.get(resultat.source, resultat.source), resultat.decision
        print(f"  DÉCISION (règles métier) -> EXPLICATION ({source}) :")
        for p in redigee.problems:
            print(f"    - Problème : {p}")
        for a in redigee.actions:
            print(f"    > [{a.priority.upper():7s}] {a.type} : {a.description}")
        print("-" * LARGEUR)
    return _afficher


# ------------------------------------------------------------------ avant / après

INDICATEURS = {
    "taux_abandon": ("Clients qui raccrochent", "%"),
    "taux_abandon_sante": ("Abandons sur la file santé", "%"),
    "respect_sla_urgence": ("Urgences prises en moins de 3 min", "%"),
    "attente_moyenne_min": ("Attente moyenne", "min"),
    "fcr": ("Résolus au premier contact (FCR)", "%"),
    "satisfaction": ("Satisfaction client (sur 5)", ""),
    "taux_occupation": ("Taux d'occupation des conseillers", "%"),
    "cout": ("Coût du personnel (points)", ""),
    "recompense_totale": ("Récompense de la journée", ""),
}


def avant_apres(scenario: str, nb_journees: int) -> pd.DataFrame:
    """Règles vs PPO sur les mêmes journées (graines d'évaluation 0..n-1)."""
    lignes = []
    for nom, policy in (("Règles (avant)", "rules"), ("Agent responsable (après)", "responsable")):
        kpi = pd.DataFrame([jouer_journee(creer_politique(policy), scenario, g) for g in range(nb_journees)])
        lignes.append({"politique": nom, **kpi[list(INDICATEURS)].mean().to_dict()})
    return pd.DataFrame(lignes).set_index("politique")


def afficher_avant_apres(df: pd.DataFrame, nb_journees: int) -> None:
    print(f"\n  AVANT / APRÈS (moyenne de {nb_journees} journées identiques pour les deux politiques)")
    print(f"  {'Indicateur':38s} {'Règles':>10s} {'Agent':>10s} {'Écart':>10s}")
    for cle, (libelle, unite) in INDICATEURS.items():
        avant, apres = df.loc["Règles (avant)", cle], df.loc["Agent responsable (après)", cle]
        echelle = 100 if unite == "%" else 1
        print(f"  {libelle:38s} {avant * echelle:9.1f}{unite[:1]:1s} {apres * echelle:9.1f}{unite[:1]:1s} "
              f"{(apres - avant) * echelle:+9.1f}{unite[:1]:1s}")


# ------------------------------------------------------------------ programme

def demo_persona(nom: str, pause: float, sans_llm: bool, nb_journees: int, detail: bool = False,
                 superviseur=None, graine=None) -> pd.DataFrame:
    persona = PERSONAS[nom]
    titre(f"PERSONA : {nom.upper()} - {persona['presentation']}")
    print("Journée simulée de 8h à 20h, pilotée par l'agent responsable (PPO + garde-fous) ; les règles jouent la même journée en parallèle.")
    bilan = jouer_macro(persona, pause, appel_persona(nom, persona, sans_llm), detail, superviseur, graine)
    p, r = bilan["ppo"], bilan["regles"]
    print(f"\n  FIN DE JOURNÉE : {p['abandons']} clients ont raccroché avec l'agent, {r['abandons']} avec les "
          f"règles (sur ~{p['recus']} appels).")
    res = bilan["resume"]
    print(f"  JOURNAL : {res['decisions_agent']} décisions de l'agent, {res['decisions_repli_regles']} replis sur les "
          f"règles, {res['propositions_couteuses']} propositions coûteuses dont {res['propositions_refusees']} "
          f"refusées, {res['decisions_peu_sures']} décisions peu sûres.")
    FICHIER_JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    FICHIER_JOURNAL.with_name(f"journal_{nom}.json").write_text(
        json.dumps(bilan["journal"], ensure_ascii=False, indent=1), encoding="utf-8")
    df = avant_apres(persona["scenario"], nb_journees)
    afficher_avant_apres(df, nb_journees)
    return df.assign(persona=nom).reset_index()


def main() -> None:
    parser = argparse.ArgumentParser(description="Démo en direct des personas")
    parser.add_argument("--persona", choices=[*PERSONAS, "tous", "crise"], default="tous",
                        help="crise = cumul jamais vu (sous-effectif + rupture + incident) : montre le repli sur les règles")
    parser.add_argument("--pause", type=float, default=0.0, help="secondes entre deux décisions affichées")
    parser.add_argument("--sans-llm", action="store_true", help="n'appelle pas Gemini (textes fixes)")
    parser.add_argument("--journees", type=int, default=NB_JOURNEES_AVANT_APRES)
    parser.add_argument("--detail", action="store_true", help="chaque quart d'heure au lieu de chaque heure")
    parser.add_argument("--superviseur", type=int, nargs="?", const=4, default=None, metavar="N",
                        help="vous validez (o/n) les N premières actions coûteuses (4 par défaut), "
                             "puis la délégation par budget prend le relais")
    parser.add_argument("--graine", type=int, default=None,
                        help="journée à jouer (par défaut : la journée médiane de chaque persona)")
    args = parser.parse_args()

    if args.persona == "crise":
        PERSONAS["crise"] = scenario_crise()
    noms = list(PERSONAS) if args.persona == "tous" else [args.persona]
    resultats = pd.concat([demo_persona(n, args.pause, args.sans_llm, args.journees, args.detail,
                                        SuperviseurConsole(args.superviseur) if args.superviseur else None, args.graine)
                           for n in noms])
    FICHIER_AVANT_APRES.parent.mkdir(parents=True, exist_ok=True)
    resultats.to_csv(FICHIER_AVANT_APRES, index=False, encoding="utf-8")
    print(f"\nAvant / après enregistré : {FICHIER_AVANT_APRES}")


if __name__ == "__main__":
    main()
