"""API FastAPI du Workforce Manager Agent (CallVerse / PharmaShop).

Lancement (depuis le dossier parent de workforce_manager/) :
    python -m uvicorn workforce_manager.api.main:app --port 8000 --reload
Documentation interactive : http://localhost:8000/docs

Endpoints
- POST /api/agents/workforce-manager               contrat openapi.yaml (+ type_demande optionnel)
- POST /api/agents/workforce-manager/simulate-day  journée simulée pas à pas (extension proposée)
- GET  /api/kpi                                    KPI de la dernière simulation (schéma Kpi)
"""

import json
import os
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from workforce_manager.api.simulation import (
    ModeleNonEntraine, SimulateDayRequest, SimulateDayResult, simuler_journee,
)
from workforce_manager.api.reponse import etendre
from workforce_manager.llm.explainer import ClientLLM, expliquer
from workforce_manager.micro.quality_rules import decide
from workforce_manager.micro.type_demande import deduire_type_demande
from workforce_manager.schemas import Kpi, WorkforceDecisionEtendue, WorkforceManagerRequest

# Front de l'équipe (Vite) : localhost et 127.0.0.1 sont deux origines différentes.
ORIGINES_FRONT = ["http://localhost:5173", "http://127.0.0.1:5173"]
DOSSIER_EXEMPLES = Path(__file__).parent / "exemples"


def _exemple(nom: str) -> dict:
    """Exemples préremplis dans la page /docs (Sami, Inès, Karim)."""
    return json.loads((DOSSIER_EXEMPLES / f"{nom}.json").read_text(encoding="utf-8"))


EXEMPLES_DECISION = {
    "ines": {"summary": "Inès – urgence enfant mal comprise", "value": _exemple("ines")},
    "sami": {"summary": "Sami – rupture de stock, info fausse", "value": _exemple("sami")},
    "karim": {"summary": "Karim – retour d'un tensiomètre", "value": _exemple("karim")},
    "contrat_strict": {"summary": "Contrat Swagger strict (sans type_demande)",
                       "value": {"evaluation": _exemple("sami")["evaluation"]}},
}
EXEMPLES_SIMULATION = {
    "sami_ppo": {"summary": "Sami – rupture, pilotée par PPO", "value": _exemple("simulate_sami_ppo")},
    "sami_none": {"summary": "Sami – sans pilotage", "value": {"scenario": "sami_rupture_stock", "policy": "none"}},
}


app = FastAPI(
    title="Workforce Manager Agent – CallVerse / PharmaShop",
    description="Agent n°4 du Digital Twin : décisions qualité (règles + explications LLM) "
                "et pilotage du centre (Reinforcement Learning).",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINES_FRONT, allow_methods=["*"], allow_headers=["*"])
api = APIRouter(prefix="/api")


# ------------------------------------------------------------------ erreurs au format Error du Swagger

@app.exception_handler(RequestValidationError)
async def requete_invalide(_: Request, exc: RequestValidationError) -> JSONResponse:
    """422 au format {code, message} (components/schemas/Error) au lieu du format FastAPI."""
    erreurs = [f"{'.'.join(str(x) for x in e['loc'][1:])} : {e['msg']}" for e in exc.errors()]
    return JSONResponse(status_code=422, content={"code": "requete_invalide", "message": " ; ".join(erreurs)})


class Error(BaseModel):
    """components/schemas/Error du Swagger de l'équipe."""
    code: str
    message: str


def erreur(statut: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=statut, content={"code": code, "message": message})


def reponses_erreur(*statuts: int) -> dict:
    """Documente dans /docs les erreurs au format Error (et non le format interne FastAPI)."""
    descriptions = {404: "Introuvable", 422: "Requête invalide", 503: "Modèle RL non entraîné"}
    return {s: {"model": Error, "description": descriptions[s]} for s in statuts}


# ------------------------------------------------------------------ dépendances (remplaçables en test)

def llm_active_par_defaut() -> bool:
    """WM_LLM=off : pas d'appel Gemini par défaut (tests d'intégration, quota gratuit de 20/jour)."""
    return os.environ.get("WM_LLM", "on").strip().lower() not in {"off", "false", "0", "non"}


def client_llm() -> Optional[ClientLLM]:
    """None = Gemini si GEMINI_API_KEY est définie, sinon textes fixes. Remplacé dans les tests."""
    return None


# ------------------------------------------------------------------ endpoints

def contexte_llm(kpi: Optional[Kpi]) -> dict:
    """Le KPI envoyé par le front sert seulement de contexte aux explications."""
    if kpi is None:
        return {}
    return {k: v for k, v in {"taux_escalade_centre_pct": kpi.tauxEscalade,
                              "qualite_moyenne_centre": kpi.qualiteReponses}.items() if v is not None}


@api.post("/agents/workforce-manager", response_model=WorkforceDecisionEtendue,
          response_model_exclude_none=True, tags=["Agents"],
          summary="Analyser scores et KPI, prendre des décisions", responses=reponses_erreur(422),
          response_description="Décisions. En-têtes : X-Explication-Source (llm, fallback, sans_objet, "
                               "desactive) et X-Type-Demande-Source (d'où vient le type de demande).")
def workforce_manager(
    response: Response,
    requete: Annotated[WorkforceManagerRequest, Body(openapi_examples=EXEMPLES_DECISION)],
    explications: Optional[bool] = Query(None, description="false : textes fixes, sans appel au LLM "
                                         "(par défaut : true, sauf si la variable WM_LLM=off)"),
    strict: bool = Query(False, description="true : uniquement problems/actions du contrat openapi.yaml"),
    client: Optional[ClientLLM] = Depends(client_llm),
):
    """Règles métier (décision) puis LLM (rédaction) ; en cas d'échec du LLM, textes fixes."""
    type_demande, provenance = deduire_type_demande(requete.type_demande, requete.request)
    response.headers["X-Type-Demande-Source"] = provenance
    decision = decide(requete.evaluation, type_demande)
    if explications is None:
        explications = llm_active_par_defaut()
    if explications:
        profil = requete.request.profile if requete.request else None
        resultat = expliquer(decision, requete.evaluation, type_demande, profil,
                             contexte_llm(requete.kpi), client=client)
        response.headers["X-Explication-Source"] = resultat.source
        decision = resultat.decision
    else:
        response.headers["X-Explication-Source"] = "desactive"
    if strict:
        return decision
    return etendre(decision, requete.evaluation, type_demande)


@api.post("/agents/workforce-manager/simulate-day", response_model=SimulateDayResult, tags=["Agents"],
          summary="Simuler une journée du centre avec une politique de pilotage",
          responses=reponses_erreur(422, 503))
def simulate_day(request: Request,
                 requete: Annotated[SimulateDayRequest, Body(openapi_examples=EXEMPLES_SIMULATION)]):
    """Déroulé des 48 quarts d'heure (actions, files, abandons) et KPI finaux au format Kpi."""
    try:
        resultat = simuler_journee(requete.scenario, requete.policy, requete.seed)
    except ModeleNonEntraine as e:
        return erreur(503, "modele_non_entraine", str(e))
    request.app.state.derniers_kpi = resultat.kpi
    return resultat


@api.get("/kpi", response_model=Kpi, tags=["KPI"], summary="KPI de la dernière simulation",
         responses=reponses_erreur(404))
def kpi(request: Request):
    derniers = getattr(request.app.state, "derniers_kpi", None)
    if derniers is None:
        return erreur(404, "aucune_simulation", "Lancer d'abord POST /api/agents/workforce-manager/simulate-day.")
    return derniers


app.include_router(api)
