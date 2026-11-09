"""Routes du Customer Advisor (Agentic RAG)."""
from typing import Optional

from fastapi import APIRouter

from backend.core.orchestrator import remember_advisor
from backend.schemas import (AdvisorRequest, AdvisorResponse, ConversationRequest, ConversationResponse,
                             ConversationTurn, HistoryTurn)
from backend.services.advisor import dump, front_fields, run_advisor

router = APIRouter()


@router.post("/api/agents/customer-advisor", response_model=AdvisorResponse, tags=["Agents"],
          summary="Traiter la demande (Agentic RAG) et générer une réponse")
def customer_advisor(req: AdvisorRequest):
    msgs = (req.conversationMessages or [])[:5] if req.isConversation else []
    if len(msgs) <= 1:
        res = run_advisor(AdvisorRequest(profile=req.profile, message=msgs[0], topic=req.topic, rag=req.rag, history=req.history)
                   if msgs else req)
        # conversation page par page : on garde la réponse complète pour l'enregistrement en base
        remember_advisor(req.conversationId, len(req.history) // 2 + 1, dump(res))
        return front_fields(res, req.rag)

    # session saisie à la main : plusieurs messages client, traités dans l'ordre avec l'historique cumulé
    history, exchanges, sources, total, res = list(req.history), [], {}, 0, None
    for i, msg in enumerate(msgs):
        res = run_advisor(AdvisorRequest(profile=req.profile, message=msg, topic=req.topic, rag=req.rag, history=history))
        history += [HistoryTurn(role="client", content=msg), HistoryTurn(role="advisor", content=res.answer)]
        exchanges.append({"turn": i + 1, "clientMessage": msg, "advisorAnswer": res.answer,
                          "sources": [dump(s) for s in res.sources], "latencyMs": res.latencyMs})
        sources.update({s.id: s for s in res.sources})
        total += res.latencyMs
    res.sources, res.latencyMs = list(sources.values()), total
    return front_fields(res, req.rag, len(msgs), exchanges)


@router.post("/api/agents/customer-advisor/conversation", response_model=ConversationResponse, tags=["Agents"],
          summary="Traiter une session multi-messages (historique conservé)")
def customer_advisor_conversation(req: ConversationRequest):
    history, turns, total = [], [], 0
    for i, msg in enumerate(req.messages):
        res = run_advisor(AdvisorRequest(profile=req.profile, message=msg, topic=req.topic, rag=req.rag, history=history))
        history += [HistoryTurn(role="client", content=msg), HistoryTurn(role="advisor", content=res.answer)]
        turns.append(ConversationTurn(turn=i + 1, clientMessage=msg, advisor=res))
        total += res.latencyMs
    return ConversationResponse(turns=turns, latencyMs=total)
