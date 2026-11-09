"""Base de connaissances : documents indexés par le RAG."""
from fastapi import APIRouter

from backend.core import agent as ag
from backend.schemas import KbDocument
from backend.services import advisor as svc

router = APIRouter()


@router.get("/api/knowledge-base/documents", response_model=list[KbDocument], tags=["Base de connaissances"],
         summary="Lister les documents indexés")
def kb_documents():
    out = []
    for name, mod in svc.AGENT.services.items():
        for i, d in enumerate(mod.docs):
            if d.get("type") in ag.EXAMPLE_TYPES:
                continue
            out.append(KbDocument(id=f"{name}-{i}", title=d.get("titre", "Document"),
                                  category=svc.MODULE_LABELS.get(name, name), excerpt=(d.get("contenu") or "")[:160]))
    return out[:200]
