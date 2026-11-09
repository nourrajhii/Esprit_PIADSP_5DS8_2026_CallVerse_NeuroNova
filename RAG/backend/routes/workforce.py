"""Workforce Manager (agent 4) et KPI."""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from backend.services import workforce

router = APIRouter()


class WorkforceEvaluation(BaseModel):
    """Rapport de l'Analyste Qualité (champs inconnus acceptés : alerts, loraRisk, priority...)."""
    model_config = ConfigDict(extra="allow")
    globalScore: Optional[int] = None
    criteria: dict[str, Optional[int]] = {}


class WorkforceProfile(BaseModel):
    profile: str = "non_precise"


class WorkforceRequest(BaseModel):
    evaluation: WorkforceEvaluation
    request: WorkforceProfile = WorkforceProfile()
    kpi: Optional[dict] = None


@router.post("/api/agents/workforce-manager", tags=["Agents"],
             summary="Analyser scores et KPI, prendre des décisions")
def workforce_manager(req: WorkforceRequest):
    return workforce.decide(req.evaluation.model_dump(), req.request.profile, req.kpi)


@router.get("/api/kpi", tags=["Agents"], summary="KPI calculés sur les évaluations de l'Analyste Qualité")
def kpi():
    return workforce.compute_kpi()
