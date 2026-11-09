"""Statut de l'API."""
from fastapi import APIRouter

from backend.core import agent as ag
from backend.core import db
from backend.services import advisor as svc

router = APIRouter()


@router.get("/api/health", tags=["Agents"], summary="Statut de l'API et du modèle")
def health():
    return {"status": "ok", "model": ag.LAST_MODEL, "agentic": ag.AGENTIC, "db": db.is_configured(),
            "modules": {n: len(m.docs) for n, m in svc.AGENT.services.items()}}
