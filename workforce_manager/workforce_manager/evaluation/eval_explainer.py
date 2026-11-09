"""Jeu de test de l'explainer LLM : 15 cas, vérifications automatiques, taux de réussite.

Lancement (depuis le dossier parent de workforce_manager/), clé requise pour le vrai test :
    $env:GEMINI_API_KEY = "..."            # PowerShell (jamais dans le code)
    python -m workforce_manager.evaluation.eval_explainer

Sorties : evaluation/resultats/eval_explainer.csv et eval_explainer_sorties.json
"""

import json
import time
from collections import Counter
from pathlib import Path

import pandas as pd

from workforce_manager.llm.explainer import Explication, expliquer
from workforce_manager.llm.verifications import NOMS_VERIFICATIONS
from workforce_manager.micro.quality_rules import decide
from workforce_manager.schemas import MockEvaluationRecord, QualityEvaluation

RACINE = Path(__file__).parent.parent
# Offre gratuite Gemini : nombre de requêtes par minute limité -> petite pause entre cas.
PAUSE_ENTRE_CAS_S = 5
FICHIER_CSV = RACINE / "evaluation" / "resultats" / "eval_explainer.csv"
FICHIER_SORTIES = RACINE / "evaluation" / "resultats" / "eval_explainer_sorties.json"


def _ev(score, **criteres) -> QualityEvaluation:
    base = dict(pertinence=85, exactitude=85, groundedness=85, empathie=85, clarte=85, conformite=85)
    return QualityEvaluation(globalScore=score, criteria={**base, **criteres})


def _mocks_par_archetype() -> dict:
    """Premier mock de chaque archétype (sauf bonne_reponse, sans action à expliquer)."""
    brut = json.loads((RACINE / "data" / "mock_evaluations.json").read_text(encoding="utf-8"))
    choix = {}
    for m in map(MockEvaluationRecord.model_validate, brut):
        if m.archetype != "bonne_reponse":
            choix.setdefault(m.archetype, m)
    return choix


def construire_cas() -> list:
    """15 cas : 3 variantes des personas (≠ des exemples few-shot), 6 archétypes, 6 cas limites."""
    cas = [
        dict(nom="persona_sami_variante", type_demande="sante", profil="mecontent",
             contexte={"evenement": "rupture de stock des capteurs de glycémie", "heure": "11h45"},
             evaluation=_ev(55, exactitude=45, empathie=35)),
        dict(nom="persona_ines_variante", type_demande="urgence", profil="nerveux",
             contexte={"evenement": "heure de pointe de fin de journée", "heure": "18h40"},
             evaluation=_ev(52, pertinence=40, clarte=50)),
        dict(nom="persona_karim_variante", type_demande="sante", profil="exigeant",
             contexte={"evenement": "lot de tensiomètres défectueux signalé", "heure": "16h00"},
             evaluation=_ev(63, groundedness=50, conformite=65)),
    ]
    for archetype, m in _mocks_par_archetype().items():
        cas.append(dict(nom=f"mock_{archetype}", type_demande=m.type_demande, profil=m.profil,
                        contexte={}, evaluation=m.evaluation))
    cas += [
        dict(nom="doublon_signaler_kb", type_demande="standard", profil="calme", contexte={},
             evaluation=_ev(60, groundedness=40, exactitude=45)),
        dict(nom="criteres_absents_sante", type_demande="sante", profil="confus", contexte={},
             evaluation=QualityEvaluation(globalScore=70, criteria={"empathie": 50, "clarte": 55})),
        dict(nom="type_inconnu_non_conforme", type_demande=None, profil=None, contexte={},
             evaluation=_ev(66, conformite=50)),
        dict(nom="garde_fou_sante_bon_score", type_demande="sante", profil="fidele", contexte={},
             evaluation=_ev(84, conformite=55)),
        dict(nom="zone_grise", type_demande="standard", profil="calme", contexte={},
             evaluation=_ev(74, pertinence=75, clarte=72)),
        dict(nom="defauts_multiples_standard", type_demande="standard", profil="impatient",
             contexte={"heure": "12h15"}, evaluation=_ev(48, clarte=35, conformite=50, empathie=40, pertinence=55)),
    ]
    assert len(cas) == 15
    return cas


def resumer(cas: dict, resultat: Explication) -> dict:
    """Une ligne par cas : source finale et vérifications en échec (tous essais confondus)."""
    en_echec = Counter(e.split(" : ")[0] for e in resultat.erreurs)
    return {
        "cas": cas["nom"], "source": resultat.source, "tentatives": resultat.tentatives,
        "reussi_1er_essai": resultat.source == "llm" and resultat.tentatives == 1,
        # Réponses réellement reçues de l'API (hors 503/429/réseau) : base du taux du PROMPT.
        "reponses_api": resultat.tentatives - en_echec.get("api", 0),
        "premier_essai_repondu": not (resultat.erreurs and resultat.erreurs[0].startswith("api")),
        **{f"echec_{nom}": en_echec.get(nom, 0) for nom in ("api", *NOMS_VERIFICATIONS)},
        "erreurs": " | ".join(resultat.erreurs),
    }


def main() -> None:
    import os
    from workforce_manager.llm.explainer import MODELE_PAR_DEFAUT
    print(f"Modèle évalué : {os.environ.get('GEMINI_MODEL', MODELE_PAR_DEFAUT)}\n")
    lignes, sorties = [], []
    for c in construire_cas():
        decision = decide(c["evaluation"], c["type_demande"])
        resultat = expliquer(decision, c["evaluation"], c["type_demande"], c["profil"], c["contexte"])
        lignes.append(resumer(c, resultat))
        sorties.append({"cas": c["nom"], "source": resultat.source,
                        "decision_regles": decision.model_dump(), "decision_redigee": resultat.decision.model_dump()})
        print(f"{c['nom']:28s} {resultat.source:9s} essais={resultat.tentatives}", flush=True)
        time.sleep(PAUSE_ENTRE_CAS_S)

    df = pd.DataFrame(lignes)
    FICHIER_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(FICHIER_CSV, index=False, encoding="utf-8")
    FICHIER_SORTIES.write_text(json.dumps(sorties, ensure_ascii=False, indent=2), encoding="utf-8")
    afficher_bilan(df)


def afficher_bilan(df: pd.DataFrame) -> None:
    """Sépare la qualité du PROMPT de la disponibilité de l'API (503, quota...)."""
    n = len(df)
    llm = df["source"] == "llm"
    evaluables = df[df["reponses_api"] > 0]
    premiers = df[df["premier_essai_repondu"] & (df["source"] != "sans_objet")]
    print(f"\n--- Disponibilité de l'API ---")
    print(f"Cas où Gemini a répondu au moins une fois   : {len(evaluables)}/{n}")
    print(f"Appels refusés par Google (503, 429...)      : {int(df['echec_api'].sum())}")
    print(f"\n--- Qualité du prompt (cas où Gemini a répondu) ---")
    if len(evaluables):
        print(f"Sortie valide, essais compris                : {llm[evaluables.index].sum()}/{len(evaluables)}"
              f" = {llm[evaluables.index].mean():.0%}")
    if len(premiers):
        print(f"Sortie valide dès le 1er essai               : {premiers['reussi_1er_essai'].sum()}/{len(premiers)}"
              f" = {premiers['reussi_1er_essai'].mean():.0%}")
    print(f"Réponses Gemini conformes / reçues           : {llm.sum()}/{int(df['reponses_api'].sum())}")
    print("Échecs par vérification (tous essais) :",
          {c.removeprefix("echec_"): int(df[c].sum()) for c in df.columns if c.startswith("echec_") and df[c].sum()})
    print(f"\n--- Bilan global (ce que reçoit l'utilisateur) ---")
    print(f"Textes rédigés par Gemini : {llm.sum()}/{n} ; textes fixes (fallback) : {(df['source'] == 'fallback').sum()}/{n}")
    if (df["source"] == "fallback").all() and df["erreurs"].str.contains("client").all():
        print("\n>> Aucune clé API : définir GEMINI_API_KEY puis relancer pour mesurer le vrai taux.")


if __name__ == "__main__":
    main()
