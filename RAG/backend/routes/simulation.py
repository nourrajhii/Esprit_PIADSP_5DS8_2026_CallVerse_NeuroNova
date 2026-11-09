"""Routes du Client Simulator et des conversations simulées (client virtuel <-> conseiller RAG)."""
from typing import Optional

from fastapi import APIRouter, HTTPException

from backend.core.orchestrator import (generate_first_message, next_question, run_conversation, session_result,
                                       start_session)
from backend.schemas import (AdvisorRequest, ClientSimRequest, HistoryTurn, SaveConversationRequest,
                             SimulationRequest)
from backend.services import history, simulation
from backend.services.advisor import dump, run_advisor

router = APIRouter()


@router.post("/api/agents/client-simulator", tags=["Agents"],
          summary="Générer le premier message d'un client virtuel")
def client_simulator(req: ClientSimRequest):
    """Message unique, ou conversation une question à la fois : le front envoie d'abord profile/topic/messageCount,
    puis conversationId + advisorMessage (réponse du conseiller) pour obtenir le message suivant du même client."""
    try:
        if req.conversationId:
            if not (req.advisorMessage or "").strip():
                raise HTTPException(400, "advisorMessage est requis pour générer le message suivant.")
            try:
                return next_question(req.conversationId, req.advisorMessage)
            except KeyError:
                raise HTTPException(404, "Conversation introuvable (le serveur a peut-être redémarré) : relancez-la.")
        if req.history:
            raise HTTPException(400, "conversationId est requis pour continuer une conversation.")
        if req.isConversation and req.messageCount > 1:
            return start_session(profile=req.profile, topic=req.topic, urgency=req.urgency,
                                 message_count=req.messageCount, custom_prompt=req.customPrompt)
        return generate_first_message(profile=req.profile, topic=req.topic, urgency=req.urgency,
                                      custom_prompt=req.customPrompt)
    except RuntimeError as e:  # Client Simulator indisponible
        raise HTTPException(503, str(e))


@router.post("/api/simulations/conversation/save", tags=["Simulation"],
             summary="Enregistrer une conversation menée page par page (Simulateur ↔ Conseiller) : base, évaluation, décision, historique")
def save_conversation(req: SaveConversationRequest):
    conv = session_result(req.conversationId, profile=req.profile, topic=req.topic, rag=req.rag,
                          turns=[dump(t) for t in req.turns], fallback_id=req.id)
    conv["saved"] = simulation.save_to_db(conv)
    # L'enregistrement en base est acquis ; si l'Analyste Qualité échoue (Gemini...), l'erreur remonte au front.
    result = simulation.build_result(conv, profile=req.profile, topic=req.topic)
    return result


def _run_global(req: SimulationRequest) -> dict:
    """Client Simulator -> Conseiller RAG -> Analyste Qualité -> Workforce Manager."""
    def advisor_fn(message: str, hist: list[dict]) -> dict:
        res = run_advisor(AdvisorRequest(profile=req.profile, message=message, topic=req.topic, rag=req.rag,
                                         history=[HistoryTurn(**h) for h in hist]))
        return dump(res)

    count = req.messageCount if req.conversationMode else 1
    try:
        conv = run_conversation(
            profile=req.profile, topic=req.topic, urgency=req.urgency, rag=req.rag,
            message_count=count, first_message=req.firstMessage or req.message,
            custom_prompt=req.customPrompt, advisor_fn=advisor_fn)
    except (RuntimeError, SystemExit) as e:  # Client Simulator indisponible
        raise HTTPException(503, str(e))
    conv["saved"] = simulation.save_to_db(conv)
    return simulation.build_result(conv, profile=req.profile, topic=req.topic)


@router.post("/api/simulations", status_code=201, tags=["Simulation"],
             summary="Simulation globale : client virtuel → conseiller RAG → analyste qualité → workforce manager")
def run_simulation(req: SimulationRequest):
    return _run_global(req)


@router.post("/api/simulations/conversation", tags=["Simulation"],
             summary="Simulation globale en conversation (1 à 5 messages)")
def run_simulation_conversation(req: SimulationRequest):
    req.conversationMode = True
    return _run_global(req)


@router.get("/api/simulations", tags=["Simulation"], summary="Lister les simulations")
def list_simulations(profile: Optional[str] = None, page: int = 1, limit: int = 20):
    items = [s for s in history.summaries() if not profile or s["profile"] == profile]
    page, limit = max(page, 1), min(max(limit, 1), 100)
    return {"total": len(items), "items": items[(page - 1) * limit: page * limit]}


@router.get("/api/simulations/{sim_id}", tags=["Simulation"], summary="Détail d'une simulation")
def get_simulation(sim_id: str):
    found = history.get(sim_id)
    if not found:
        raise HTTPException(404, "Simulation introuvable")
    return found


@router.get("/api/conversations", tags=["Simulation"], summary="Historique des conversations (barre latérale)")
def conversations():
    return history.summaries()
