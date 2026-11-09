"""Simulation globale : Client Simulator -> Conseiller RAG -> Analyste Qualité -> Workforce Manager.

Le résultat a la forme attendue par le front (SimulationResult) : request / response / evaluation / decision,
plus `exchanges` (un élément par tour) pour une conversation de plusieurs messages.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from backend.core import db
from backend.core.orchestrator import LABELS, SENTIMENTS
from backend.quality import router as quality
from backend.services import history, workforce

CRITERIA = quality.CRITERIA
PRIORITY_ORDER = ["faible", "moyen", "eleve", "critique"]


def _evaluate_turn(conv_id: str, profile: str, turn: dict) -> dict:
    """Rapport de l'Analyste Qualité pour un tour (Gemini + règles de sécurité + RAG + LoRA si activé)."""
    adv = turn["advisor"]
    sources = [{"id": s.get("id"), "title": s.get("title"), "score": s.get("score"), "content": s.get("snippet")}
               for s in adv.get("sources") or []]
    payload = quality.EvaluationInput.model_validate({
        "request": {"message": turn["clientMessage"], "profile": profile},
        "response": {"answer": adv["answer"], "sources": sources},
        "conversationId": f"{conv_id}-t{turn['turn']}",
    })
    return quality.evaluate(payload)


def _unique(items: list[str], limit: int = 6) -> list[str]:
    return list(dict.fromkeys(i for i in items if i))[:limit]


def _aggregate(reports: list[dict]) -> dict:
    """Évaluation de la conversation : moyenne des tours ; un critère `None` reste non vérifié."""
    criteria = {}
    for k in CRITERIA:
        vals = [r["criteria"][k] for r in reports if r["criteria"].get(k) is not None]
        criteria[k] = round(sum(vals) / len(vals)) if vals else None
    lora = next((r["loraRisk"] for r in reports if (r.get("loraRisk") or {}).get("label") == "CRITIQUE"),
                reports[-1].get("loraRisk"))
    return {
        "globalScore": round(sum(r["globalScore"] for r in reports) / len(reports)),
        "criteria": criteria,
        "strengths": _unique([s for r in reports for s in r["strengths"]]),
        "improvements": _unique([s for r in reports for s in r["improvements"]]),
        "recommendations": _unique([s for r in reports for s in r["recommendations"]]),
        "alerts": _unique([a for r in reports for a in r["alerts"]]),
        "priority": max((r["priority"] for r in reports), key=PRIORITY_ORDER.index),
        "requiresHumanReview": any(r.get("requiresHumanReview") for r in reports),
        "accuracyStatus": reports[0].get("accuracyStatus"),
        "loraRisk": lora,
        "ragReference": reports[-1].get("ragReference"),
        "mode": reports[-1].get("mode"),
        "profile": reports[-1].get("profile"),
    }


def build_result(conv: dict, *, profile: str, topic: Optional[str]) -> dict:
    """conv = résultat d'orchestrator.run_conversation / session_result. Lève HTTPException si l'Analyste Qualité échoue."""
    turns = conv["turns"]
    with ThreadPoolExecutor(max_workers=min(3, len(turns))) as pool:
        reports = list(pool.map(lambda t: _evaluate_turn(conv["id"], profile, t), turns))

    exchanges = [{
        "turn": t["turn"],
        "client": {"message": t["clientMessage"], "profile": profile, "profileLabel": LABELS.get(profile, profile),
                   "sentiment": SENTIMENTS.get(profile, "neutre") if t["turn"] == 1 else "neutre"},
        "advisor": {"answer": t["advisor"]["answer"], "latencyMs": t["advisor"].get("latencyMs", 0),
                    "sources": [{"id": s.get("id"), "title": s.get("title"), "score": s.get("score", 0)}
                                for s in t["advisor"].get("sources") or []]},
        "evaluation": {"globalScore": r["globalScore"], "criteria": r["criteria"], "alerts": r["alerts"],
                       "requiresHumanReview": r.get("requiresHumanReview", False)},
    } for t, r in zip(turns, reports)]

    evaluation = _aggregate(reports)
    decision = workforce.decide(evaluation, profile, workforce.compute_kpi())
    first, last = turns[0], turns[-1]
    count = len(turns)
    msg = first["clientMessage"]
    result = {
        "id": conv["id"],
        "createdAt": conv["createdAt"],
        "title": ("💬 " + msg[:35] + f" ({count} msg)") if count > 1 else msg[:40],
        "profile": profile,
        "score": evaluation["globalScore"],
        "topic": topic or "auto",
        "isConversation": count > 1,
        "messageCount": count,
        "client": conv.get("client", {}),
        "clientModel": conv.get("clientModel"),
        "advisorModel": conv.get("advisorModel"),
        "saved": conv.get("saved", False),  # True = conversation enregistrée dans PostgreSQL
        "request": {"profile": profile, "message": msg, "intent": first["advisor"].get("intent", "demande_generale"),
                    "entities": conv.get("client", {})},
        "response": {"answer": last["advisor"]["answer"], "intent": last["advisor"].get("intent", "demande_generale"),
                     "sources": exchanges[0]["advisor"]["sources"] if count == 1 else exchanges[-1]["advisor"]["sources"],
                     "latencyMs": sum(e["advisor"]["latencyMs"] for e in exchanges)},
        "exchanges": exchanges,
        "evaluation": evaluation,
        "decision": decision,
    }

    # --- Persistance PostgreSQL : qualité + workforce ---
    try:
        db.save_quality_evaluation(conv["id"], evaluation)
    except Exception as e:
        print(f"  [db] qualité non enregistrée : {type(e).__name__}: {str(e)[:200]}")
    try:
        db.save_workforce_decision(conv["id"], decision)
    except Exception as e:
        print(f"  [db] workforce non enregistré : {type(e).__name__}: {str(e)[:200]}")

    history.add(result)
    return result


def save_to_db(conv: dict) -> bool:
    try:
        return db.save_conversation(conv)
    except Exception as e:  # la simulation reste valide même si l'enregistrement échoue
        print(f"  [db] enregistrement impossible : {type(e).__name__}: {str(e)[:200]}")
        return False
