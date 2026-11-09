"""Niveau micro : une QualityEvaluation -> une WorkforceDecision (règles métier).

Lancement de la démonstration (depuis le dossier parent de workforce_manager/) :
    python -m workforce_manager.micro.quality_rules

Échelle supposée des critères : 0..100, comme globalScore (hypothèse de l'étape 1).
Les textes « problems » et « description » sont fixes : l'étape 7 les fera rédiger par le LLM.
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional

from workforce_manager.schemas import Action, QualityEvaluation, TypeDemande, WorkforceDecision

CRITERES = ("pertinence", "exactitude", "groundedness", "empathie", "clarte", "conformite")

# ---------------------------------------------------------------- seuils métier
# 60/100 = « insuffisant » : sous ce seuil, la réponse a un défaut net sur ce critère.
SEUIL_INSUFFISANT = 60
# Conformité plus exigeante (70) : sur un produit de santé, une réponse « presque
# conforme » (posologie sans renvoi au pharmacien...) est déjà un risque réglementaire.
SEUIL_CONFORMITE = 70
# Au-dessus de 80, la réponse atteint l'objectif qualité : pas d'action corrective...
SEUIL_BONNE_REPONSE = 80
# ... SAUF deux garde-fous, car une moyenne élevée peut masquer un vrai défaut :
#  - santé : une non-conformité sur une demande santé/urgence (constat « critique ») ;
#  - défaut grave : un critère sous 40 (ex. empathie 15 face à un client nerveux ; avec un
#    poids de 10 % dans le score global, ce défaut passerait inaperçu).
SEUIL_GRAVE = 40

# Une urgence est une demande santé, en plus grave : elle suit toutes les règles santé.
TYPES_SANTE = {"sante", "urgence"}

RANG_PRIORITE = {"haute": 0, "moyenne": 1, "basse": 2}
ORDRE_TYPES = ("escalade_humain", "relancer_rag", "signaler_kb", "ajuster_reponse", "formation")


@dataclass
class Constat:
    """Un problème détecté et les actions qu'il déclenche."""
    probleme: str
    actions: List[Action] = field(default_factory=list)
    critique: bool = False          # True : s'applique même si globalScore >= 80
    valeur: Optional[int] = None    # note du critère en cause (pour détecter un défaut grave)

    def s_applique_si_bon_score(self) -> bool:
        return self.critique or (self.valeur is not None and self.valeur < SEUIL_GRAVE)


def _action(type_: str, priorite: str, description: str) -> Action:
    return Action(type=type_, description=description, priority=priorite)


# ---------------------------------------------------------------- règles (une fonction = une règle)

def regle_groundedness(c: dict, type_demande) -> List[Constat]:
    """Réponse non appuyée sur les sources : risque d'information inventée sur un produit."""
    if c["groundedness"] is None or c["groundedness"] >= SEUIL_INSUFFISANT:
        return []
    return [Constat("La réponse s'appuie peu sur les documents de la base (risque d'information inventée).", [
        _action("relancer_rag", "haute", "Relancer la recherche documentaire avec une requête reformulée."),
        _action("signaler_kb", "haute", "Vérifier que la base contient bien l'information demandée."),
    ], valeur=c["groundedness"])]


def regle_exactitude(c: dict, type_demande) -> List[Constat]:
    """Information fausse : souvent une fiche produit erronée ou obsolète dans la base."""
    if c["exactitude"] is None or c["exactitude"] >= SEUIL_INSUFFISANT:
        return []
    return [Constat("La réponse contient des informations inexactes.", [
        _action("signaler_kb", "haute", "Faire corriger la fiche ou le document source erroné."),
    ], valeur=c["exactitude"])]


def regle_empathie(c: dict, type_demande) -> List[Constat]:
    """Manque d'empathie : défaut de savoir-être, se corrige par la formation."""
    if c["empathie"] is None or c["empathie"] >= SEUIL_INSUFFISANT:
        return []
    return [Constat("Le ton manque d'empathie face à la situation du client.", [
        _action("formation", "moyenne", "Module de formation : accueil des clients inquiets ou mécontents."),
    ], valeur=c["empathie"])]


def regle_conformite(c: dict, type_demande) -> List[Constat]:
    """Non-conformité : escalade si santé (ou type inconnu, par précaution), sinon correction."""
    if c["conformite"] is None or c["conformite"] >= SEUIL_CONFORMITE:
        return []
    # Type inconnu : traité comme santé. Escalader à tort coûte un peu de temps humain ;
    # laisser passer un conseil santé non conforme peut mettre un patient en danger.
    if type_demande is None or type_demande in TYPES_SANTE:
        return [Constat("Réponse non conforme sur une demande de santé.", [
            _action("escalade_humain", "haute", "Transférer au pharmacien conseil avant tout envoi au client."),
        ], critique=True, valeur=c["conformite"])]
    return [Constat("Réponse non conforme aux règles PharmaShop (CGV, procédures).", [
        _action("ajuster_reponse", "moyenne", "Reprendre la réponse selon la procédure officielle."),
    ], valeur=c["conformite"])]


def regle_pertinence(c: dict, type_demande) -> List[Constat]:
    """Réponse à côté de la question. En urgence (cas d'Inès) : l'urgence n'a pas été comprise."""
    if c["pertinence"] is None or c["pertinence"] >= SEUIL_INSUFFISANT:
        return []
    if type_demande == "urgence":
        return [Constat("L'urgence du client n'a pas été prise en compte.", [
            _action("escalade_humain", "haute", "Prise en charge immédiate par un conseiller humain."),
        ], critique=True, valeur=c["pertinence"])]
    return [Constat("La réponse ne traite pas vraiment la question posée.", [
        _action("relancer_rag", "moyenne", "Relancer la recherche sur la vraie intention du client."),
    ], valeur=c["pertinence"])]


def regle_clarte(c: dict, type_demande) -> List[Constat]:
    """Manque de clarté : contenu juste mais mal formulé, simple reformulation."""
    if c["clarte"] is None or c["clarte"] >= SEUIL_INSUFFISANT:
        return []
    return [Constat("La réponse est confuse ou trop technique.", [
        _action("ajuster_reponse", "basse", "Reformuler en étapes courtes, sans jargon."),
    ], valeur=c["clarte"])]


def regle_conformite_non_evaluee(c: dict, type_demande) -> List[Constat]:
    """Demande santé dont la conformité n'a pas été évaluée : on ne peut pas la garantir."""
    if c["conformite"] is not None or not (type_demande is None or type_demande in TYPES_SANTE):
        return []
    return [Constat("Conformité non évaluée sur une demande de santé.", [
        _action("escalade_humain", "moyenne", "Faire vérifier la conformité par le pharmacien conseil."),
    ], critique=True)]


REGLES = (regle_conformite, regle_pertinence, regle_groundedness, regle_exactitude,
          regle_empathie, regle_clarte, regle_conformite_non_evaluee)


# ---------------------------------------------------------------- assemblage

def _criteres(evaluation: QualityEvaluation) -> dict:
    """Critères sous forme de dict ; un critère absent vaut None."""
    brut = evaluation.criteria.model_dump() if evaluation.criteria else {}
    return {nom: brut.get(nom) for nom in CRITERES}


def _fusionner(actions: List[Action]) -> List[Action]:
    """Une seule action par type : priorité la plus haute, descriptions regroupées."""
    par_type = {}
    for a in actions:
        if a.type not in par_type:
            par_type[a.type] = a.model_copy()
            continue
        garde = par_type[a.type]
        if RANG_PRIORITE[a.priority] < RANG_PRIORITE[garde.priority]:
            garde.priority = a.priority
        if a.description not in garde.description:
            garde.description = f"{garde.description} {a.description}"
    return sorted(par_type.values(), key=lambda a: (RANG_PRIORITE[a.priority], ORDRE_TYPES.index(a.type)))


def _constat_zone_grise(score: Optional[int]) -> List[Constat]:
    """Score sous l'objectif sans critère isolé en défaut : relecture légère."""
    if score is None or score >= SEUIL_BONNE_REPONSE:
        return []
    return [Constat("Qualité globale sous l'objectif, sans défaut isolé.", [
        _action("ajuster_reponse", "basse", "Relire et améliorer la réponse avant envoi."),
    ])]


def decide(evaluation: Optional[QualityEvaluation], type_demande: Optional[TypeDemande] = None) -> WorkforceDecision:
    """Applique les règles et renvoie une décision conforme au contrat openapi.yaml.

    type_demande : "standard", "sante", "urgence", ou None si inconnu (le contrat ne le
    transmet pas) ; None est traité comme une demande santé pour les règles de sécurité.
    """
    evaluation = evaluation or QualityEvaluation()
    criteres = _criteres(evaluation)
    score = evaluation.globalScore

    constats = [c for regle in REGLES for c in regle(criteres, type_demande)]
    if score is not None and score >= SEUIL_BONNE_REPONSE:
        constats = [c for c in constats if c.s_applique_si_bon_score()]   # garde-fous seulement
    elif not any(c.actions for c in constats):
        constats += _constat_zone_grise(score)

    problemes = list(dict.fromkeys(c.probleme for c in constats))
    absents = [nom for nom, v in criteres.items() if v is None]
    if absents:
        problemes.append(f"Critères non évalués : {', '.join(absents)}.")
    actions = _fusionner([a for c in constats for a in c.actions])
    return WorkforceDecision(problems=problemes, actions=actions)


# ---------------------------------------------------------------- démonstration

def _demo() -> None:
    import json
    from pathlib import Path

    from workforce_manager.schemas import MockEvaluationRecord

    chemin = Path(__file__).parent.parent / "data" / "mock_evaluations.json"
    mocks = [MockEvaluationRecord.model_validate(m) for m in json.loads(chemin.read_text(encoding="utf-8"))]
    print("=== Exemple par archétype ===")
    vus = set()
    for m in mocks:
        if m.archetype in vus:
            continue
        vus.add(m.archetype)
        d = decide(m.evaluation, m.type_demande)
        actions = ", ".join(f"{a.type}({a.priority})" for a in d.actions) or "aucune"
        print(f"{m.archetype:22s} {m.type_demande:8s} score {m.evaluation.globalScore:3d} -> {actions}")

    print("\n=== Actions déclenchées sur les 200 mocks, par archétype ===")
    par_archetype = {}
    for m in mocks:
        types = [a.type for a in decide(m.evaluation, m.type_demande).actions]
        par_archetype.setdefault(m.archetype, Counter()).update(types or ["aucune"])
    for archetype, compte in par_archetype.items():
        print(f"  {archetype:22s} {dict(compte.most_common())}")


if __name__ == "__main__":
    _demo()
