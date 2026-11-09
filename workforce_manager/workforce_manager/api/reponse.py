"""Réponse étendue de POST /agents/workforce-manager (champs lus par le front de l'équipe).

Tout est calculé de façon déterministe à partir de la décision des règles : le LLM ne
touche ni aux responsables, ni au statut, ni au résumé.
"""

from datetime import datetime, timezone
from typing import Optional

from workforce_manager.schemas import (
    ActionEtendue, QualityEvaluation, WorkforceDecision, WorkforceDecisionEtendue, WorkforceSummary,
)

NOM_AGENT = "Workforce Manager Agent"

# Qui doit agir, pour chaque type d'action (rôles du centre PharmaShop).
RESPONSABLES = {
    "relancer_rag": "Équipe IA (Customer Advisor)",
    "signaler_kb": "Responsable base documentaire",
    "ajuster_reponse": "Conseiller en charge",
    "formation": "RH & Formation",
}
# L'escalade dépend du type de demande : un conseil santé relève du pharmacien,
# une urgence du superviseur de plateau (prise en charge immédiate), le reste du niveau 2.
RESPONSABLES_ESCALADE = {
    "sante": "Pharmacien conseil",
    "urgence": "Superviseur de plateau (urgence)",
    "standard": "Superviseur équipe N2",
    None: "Pharmacien conseil",            # type inconnu : précaution santé
}
MODULE_FORMATION = "Accueil des clients inquiets ou mécontents"


def responsable(type_action: str, type_demande: Optional[str]) -> str:
    if type_action == "escalade_humain":
        return RESPONSABLES_ESCALADE.get(type_demande, RESPONSABLES_ESCALADE[None])
    return RESPONSABLES[type_action]


def resume(decision: WorkforceDecision, type_demande: Optional[str]) -> WorkforceSummary:
    types = {a.type for a in decision.actions or []}
    if "escalade_humain" in types:
        impact = f"+1 prise en charge humaine ({responsable('escalade_humain', type_demande)})"
    else:
        impact = "Traitement autonome"
    return WorkforceSummary(
        staffingImpact=impact,
        trainingModuleSuggested=MODULE_FORMATION if "formation" in types else "Aucune",
        kbUpdateRequired="signaler_kb" in types,
    )


def etendre(decision: WorkforceDecision, evaluation: Optional[QualityEvaluation],
            type_demande: Optional[str]) -> WorkforceDecisionEtendue:
    """Décision du contrat -> sur-ensemble attendu par le front."""
    actions = [ActionEtendue(**a.model_dump(), responsible=responsable(a.type, type_demande))
               for a in decision.actions or []]
    return WorkforceDecisionEtendue(
        problems=decision.problems or [],
        actions=actions,
        agent=NOM_AGENT,
        auditScore=evaluation.globalScore if evaluation else None,
        # Statut cohérent avec la décision (et non un seuil de score à part) : une réponse
        # à 85/100 mais non conforme sur la santé demande quand même une intervention.
        status="INTERVENTION_REQUISE" if actions else "OPTIMAL",
        typeDemande=type_demande,
        workforceSummary=resume(decision, type_demande),
        decidedAt=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
