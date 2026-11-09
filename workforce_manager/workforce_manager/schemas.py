"""Modèles Pydantic du Workforce Manager.

Partie 1 – CONTRAT (openapi.yaml, components/schemas) : reproduit à l'identique.
  - Aucun champ n'est obligatoire : le Swagger ne déclare pas de `required`.
  - Les bornes 0..100 n'existent que sur `globalScore` (comme dans le Swagger).
  - `extra="forbid"` : on refuse tout champ hors contrat, pour détecter
    immédiatement une faute de frappe ou un écart avec les autres agents.

Partie 2 – MODÈLES INTERNES (hors contrat) : utilisés seulement par nos mocks
et notre simulateur. Ils ne sont jamais renvoyés par l'API.
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Énumérations du contrat
# ---------------------------------------------------------------------------

# components/schemas/ProfileType
ProfileType = Literal[
    "calme", "impatient", "nerveux", "mecontent", "fidele", "confus", "exigeant"
]

# WorkforceDecision.actions[].type
ActionType = Literal[
    "ajuster_reponse", "relancer_rag", "escalade_humain", "signaler_kb", "formation"
]

# WorkforceDecision.actions[].priority
Priority = Literal["basse", "moyenne", "haute"]

# Nature de la demande client (extension proposée du contrat, voir WorkforceManagerRequest)
TypeDemande = Literal["standard", "sante", "urgence"]


class ContractModel(BaseModel):
    """Base commune : refuse les champs inconnus (contrat strict)."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# QualityEvaluation (entrée du Workforce Manager)
# ---------------------------------------------------------------------------

class Criteria(ContractModel):
    """QualityEvaluation.criteria : 6 notes entières (échelle non fixée par le Swagger)."""

    pertinence: Optional[int] = None
    exactitude: Optional[int] = None
    groundedness: Optional[int] = None
    empathie: Optional[int] = None
    clarte: Optional[int] = None
    conformite: Optional[int] = None


class QualityEvaluation(ContractModel):
    """Évaluation produite par le Quality Analyst Agent."""

    globalScore: Optional[int] = Field(default=None, ge=0, le=100)
    criteria: Optional[Criteria] = None
    strengths: Optional[List[str]] = None
    improvements: Optional[List[str]] = None
    recommendations: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# WorkforceDecision (sortie du Workforce Manager)
# ---------------------------------------------------------------------------

class Action(ContractModel):
    """Une action corrective décidée par le Workforce Manager."""

    type: Optional[ActionType] = None
    description: Optional[str] = None
    priority: Optional[Priority] = None


class WorkforceDecision(ContractModel):
    """Décision renvoyée par POST /agents/workforce-manager."""

    problems: Optional[List[str]] = None
    actions: Optional[List[Action]] = None


class PerformanceProfil(ContractModel):
    """Kpi.performanceParProfil[] : qualité moyenne et volume par profil client."""

    profile: Optional[ProfileType] = None
    score: Optional[float] = None
    count: Optional[int] = None


class Kpi(ContractModel):
    """components/schemas/Kpi : indicateurs du centre (GET /kpi)."""

    qualiteReponses: Optional[float] = None
    tauxResolution: Optional[float] = None
    tempsTraitementSec: Optional[float] = None
    tauxEscalade: Optional[float] = None
    satisfactionClient: Optional[float] = None
    performanceParProfil: Optional[List[PerformanceProfil]] = None


class RequeteClient(ContractModel):
    """Sous-ensemble souple de components/schemas/ClientRequest.

    Dans le Swagger, profile et message sont obligatoires ; ici tout est facultatif car
    le front n'envoie parfois que le profil. Sert de CONTEXTE (type de demande, profil).
    """

    profile: Optional[ProfileType] = None
    message: Optional[str] = None
    intent: Optional[str] = None
    entities: Optional[Dict[str, str]] = None


class WorkforceManagerRequest(ContractModel):
    """Corps de la requête POST /agents/workforce-manager.

    EXTENSIONS DU CONTRAT (proposées à l'équipe : docs/openapi_workforce_manager_v2.yaml),
    toutes OPTIONNELLES : une requête du Swagger actuel (uniquement `evaluation`) reste valide.
    - `type_demande` : nature de la demande ; sinon déduite de `request`, sinon précaution santé ;
    - `request` : la demande du client (ce qu'envoie déjà le front) ;
    - `kpi` : contexte du centre (accepté pour compatibilité avec le front, non utilisé
      pour décider, transmis au LLM comme contexte).
    """

    evaluation: Optional[QualityEvaluation] = None
    type_demande: Optional[TypeDemande] = None
    request: Optional[RequeteClient] = None
    kpi: Optional[Kpi] = None


# ---------------------------------------------------------------------------
# Réponse étendue (extension proposée) : ce que la page du front affiche en plus
# ---------------------------------------------------------------------------

class ActionEtendue(Action):
    """Action du contrat + `responsible` (qui doit agir, rôle PharmaShop)."""

    responsible: Optional[str] = None


class WorkforceSummary(ContractModel):
    staffingImpact: Optional[str] = None
    trainingModuleSuggested: Optional[str] = None
    kbUpdateRequired: Optional[bool] = None


class WorkforceDecisionEtendue(WorkforceDecision):
    """WorkforceDecision du contrat + champs optionnels lus par le front.

    Sur-ensemble : un client qui ne lit que problems/actions reste compatible.
    `?strict=true` renvoie la WorkforceDecision du contrat, sans ces champs.
    """

    actions: Optional[List[ActionEtendue]] = None
    agent: Optional[str] = None
    auditScore: Optional[int] = None
    status: Optional[Literal["OPTIMAL", "INTERVENTION_REQUISE"]] = None
    typeDemande: Optional[TypeDemande] = None
    workforceSummary: Optional[WorkforceSummary] = None
    decidedAt: Optional[str] = None


# ---------------------------------------------------------------------------
# Modèles internes (HORS contrat) – mocks et simulation
# ---------------------------------------------------------------------------

# Archétype de qualité ayant servi à générer le mock (vérité terrain pour l'évaluation)
Archetype = Literal[
    "bonne_reponse",
    "groundedness_faible",
    "empathie_faible",
    "non_conformite_sante",
    "kb_manquante",
    "clarte_faible",
    "urgence_mal_geree",
]


class MockEvaluationRecord(ContractModel):
    """Un enregistrement de data/mock_evaluations.json.

    Le contexte (type_demande, profil, archetype) est stocké À CÔTÉ de
    l'évaluation : `evaluation` reste un QualityEvaluation 100 % conforme.
    """

    id: str
    type_demande: TypeDemande
    profil: ProfileType
    archetype: Archetype
    evaluation: QualityEvaluation
