"""Routes Dashboard BI — données agrégées depuis PostgreSQL pour le front React."""
import json
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.core import db
from backend.core.db import _connect, is_configured

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard BI"])

# Chemin SQLite (fallback si PostgreSQL non configuré)
SQLITE_PATH = Path(__file__).resolve().parent.parent / "quality" / "quality_evaluations.sqlite3"


def _pg(sql: str, params=None) -> list[dict]:
    """Exécute une requête PostgreSQL et retourne une liste de dicts."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or [])
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


# ── DISTRIBUTION CLIENTS PAR PROFIL ──────────────────────────────────────────
@router.get("/client-distribution")
def get_client_distribution():
    if not is_configured():
        return []
    try:
        rows = _pg("""
            SELECT
                c.profile,
                COUNT(DISTINCT c.id)                                     AS nb_conversations,
                COUNT(DISTINCT cl.id)                                    AS nb_clients,
                ROUND(100.0 * COUNT(DISTINCT c.id)
                    / NULLIF(SUM(COUNT(DISTINCT c.id)) OVER (), 0), 1)   AS pct_conversations
            FROM sim_conversations c
            LEFT JOIN sim_clients cl ON cl.id = c.client_id
            GROUP BY c.profile
            ORDER BY nb_conversations DESC
        """)
        total_clients = sum(r.get("nb_clients") or 0 for r in rows)
        return [
            {
                "profile": r["profile"],
                "nbConversations": int(r["nb_conversations"] or 0),
                "nbClients": int(r["nb_clients"] or 0),
                "pctConversations": float(r["pct_conversations"] or 0),
                "pctClients": round(100 * int(r["nb_clients"] or 0) / max(total_clients, 1), 1),
            }
            for r in rows
        ]
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


def _sqlite_fallback() -> dict:
    """Fallback : calcule les KPIs depuis SQLite si PostgreSQL absent."""
    if not SQLITE_PATH.exists():
        return {}
    with sqlite3.connect(SQLITE_PATH) as conn:
        rows = conn.execute(
            "SELECT global_score, report_json FROM evaluations"
        ).fetchall()
    if not rows:
        return {}
    reports = [(score, json.loads(rj)) for score, rj in rows]
    n = len(reports)
    escalated = sum(bool(r.get("requiresHumanReview")) for _, r in reports)
    resolved = sum(s >= 75 and not r.get("requiresHumanReview") for s, r in reports)
    by_profile: dict[str, list] = {}
    for score, r in reports:
        by_profile.setdefault(r.get("profile") or "non_précisé", []).append(score)
    return {
        "nbConversations": n,
        "scoreMoyen": round(sum(s for s, _ in reports) / n, 1),
        "tauxResolution": round(100 * resolved / n, 1),
        "tauxEscalade": round(100 * escalated / n, 1),
        "alertesCritiques": sum(r.get("priority") == "critique" for _, r in reports),
        "latenceMoyMs": None,
        "source": "sqlite_fallback",
        "performanceParProfil": [
            {"profile": p, "score": round(sum(v) / len(v), 1), "nb": len(v)}
            for p, v in sorted(by_profile.items())
        ],
    }


# ── KPIs GLOBAUX ──────────────────────────────────────────────────────────────
@router.get("/kpis")
def get_kpis():
    if not is_configured():
        return _sqlite_fallback() or {"source": "empty"}
    try:
        rows = _pg("""
            SELECT
                COUNT(DISTINCT c.id)                                          AS nb_conversations,
                ROUND(AVG(q.global_score)::NUMERIC, 1)                        AS score_moyen,
                ROUND(100.0 * COUNT(CASE WHEN w.status='OPTIMAL' THEN 1 END)
                    / NULLIF(COUNT(DISTINCT c.id), 0), 1)                     AS taux_resolution,
                ROUND(100.0 * COUNT(CASE WHEN w.has_escalation THEN 1 END)
                    / NULLIF(COUNT(DISTINCT c.id), 0), 1)                     AS taux_escalade,
                COUNT(CASE WHEN q.priority='critique' THEN 1 END)             AS alertes_critiques,
                ROUND(AVG(c.total_latency_ms)::NUMERIC, 0)                    AS latence_moy_ms
            FROM sim_conversations c
            LEFT JOIN quality_evaluations q ON q.conversation_id = c.id
            LEFT JOIN workforce_decisions  w ON w.conversation_id = c.id
        """)
        r = rows[0] if rows else {}
        return {
            "nbConversations": r.get("nb_conversations", 0),
            "scoreMoyen": float(r["score_moyen"]) if r.get("score_moyen") else None,
            "tauxResolution": float(r["taux_resolution"]) if r.get("taux_resolution") else None,
            "tauxEscalade": float(r["taux_escalade"]) if r.get("taux_escalade") else None,
            "alertesCritiques": int(r.get("alertes_critiques") or 0),
            "latenceMoyMs": int(r["latence_moy_ms"]) if r.get("latence_moy_ms") else None,
            "source": "postgresql",
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── SCORES PAR CRITÈRE ────────────────────────────────────────────────────────
@router.get("/criteria")
def get_criteria():
    if not is_configured():
        return []
    try:
        rows = _pg("""
            SELECT
                ROUND(AVG(score_pertinence)::NUMERIC, 1)   AS pertinence,
                ROUND(AVG(score_exactitude)::NUMERIC, 1)   AS exactitude,
                ROUND(AVG(score_groundedness)::NUMERIC, 1) AS groundedness,
                ROUND(AVG(score_empathie)::NUMERIC, 1)     AS empathie,
                ROUND(AVG(score_clarte)::NUMERIC, 1)       AS clarte,
                ROUND(AVG(score_conformite)::NUMERIC, 1)   AS conformite
            FROM quality_evaluations
        """)
        if not rows:
            return []
        r = rows[0]
        return [
            {"criterion": "Pertinence",   "score": float(r["pertinence"])   if r["pertinence"]   else None},
            {"criterion": "Exactitude",   "score": float(r["exactitude"])   if r["exactitude"]   else None},
            {"criterion": "Groundedness", "score": float(r["groundedness"]) if r["groundedness"] else None},
            {"criterion": "Empathie",     "score": float(r["empathie"])     if r["empathie"]     else None},
            {"criterion": "Clarté",       "score": float(r["clarte"])       if r["clarte"]       else None},
            {"criterion": "Conformité",   "score": float(r["conformite"])   if r["conformite"]   else None},
        ]
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── PERFORMANCE PAR PROFIL ────────────────────────────────────────────────────
@router.get("/profiles")
def get_profiles():
    if not is_configured():
        return []
    try:
        rows = _pg("SELECT * FROM v_profile_perf ORDER BY avg_quality_score DESC NULLS LAST")
        return [
            {
                "profile": r["profile"],
                "nb": int(r["nb_conversations"] or 0),
                "score": float(r["avg_quality_score"]) if r["avg_quality_score"] else None,
                "empathie": float(r["avg_empathie"]) if r["avg_empathie"] else None,
                "pertinence": float(r["avg_pertinence"]) if r["avg_pertinence"] else None,
                "conformite": float(r["avg_conformite"]) if r["avg_conformite"] else None,
                "escaladeRate": float(r["escalation_rate_pct"]) if r["escalation_rate_pct"] else None,
                "criticalRate": float(r["critical_alert_rate_pct"]) if r["critical_alert_rate_pct"] else None,
            }
            for r in rows
        ]
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── TENDANCES JOURNALIÈRES ────────────────────────────────────────────────────
@router.get("/trends")
def get_trends(days: int = 30):
    if not is_configured():
        return []
    try:
        rows = _pg("""
            SELECT * FROM v_daily_kpis
            WHERE day >= CURRENT_DATE - INTERVAL '%s days'
            ORDER BY day ASC
        """, [days])
        return [
            {
                "day": str(r["day"]),
                "nbConversations": int(r["nb_conversations"] or 0),
                "scoreMoyen": float(r["avg_quality_score"]) if r["avg_quality_score"] else None,
                "empathie": float(r["avg_empathie"]) if r["avg_empathie"] else None,
                "pertinence": float(r["avg_pertinence"]) if r["avg_pertinence"] else None,
                "clarte": float(r["avg_clarte"]) if r["avg_clarte"] else None,
                "conformite": float(r["avg_conformite"]) if r["avg_conformite"] else None,
                "latenceMoyMs": int(r["avg_latency_ms"]) if r["avg_latency_ms"] else None,
                "nbEscalades": int(r["nb_escalations"] or 0),
                "escaladeRate": float(r["escalation_rate_pct"]) if r["escalation_rate_pct"] else None,
                "nbAlerteCritiques": int(r["nb_critical_alerts"] or 0),
                "resolutionRate": float(r["resolution_rate_pct"]) if r["resolution_rate_pct"] else None,
            }
            for r in rows
        ]
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── DISTRIBUTION DES SCORES ───────────────────────────────────────────────────
@router.get("/score-distribution")
def get_score_distribution():
    if not is_configured():
        return []
    try:
        rows = _pg("""
            SELECT
                CASE
                    WHEN global_score < 40 THEN '0-39'
                    WHEN global_score < 60 THEN '40-59'
                    WHEN global_score < 75 THEN '60-74'
                    WHEN global_score < 90 THEN '75-89'
                    ELSE '90-100'
                END AS range,
                COUNT(*) AS nb
            FROM quality_evaluations
            WHERE global_score IS NOT NULL
            GROUP BY 1 ORDER BY 1
        """)
        return [{"range": r["range"], "nb": int(r["nb"])} for r in rows]
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── STATUT WORKFORCE ──────────────────────────────────────────────────────────
@router.get("/workforce-stats")
def get_workforce_stats():
    if not is_configured():
        return {}
    try:
        rows = _pg("""
            SELECT
                COUNT(CASE WHEN status='OPTIMAL' THEN 1 END)             AS optimal,
                COUNT(CASE WHEN status='INTERVENTION_REQUISE' THEN 1 END) AS intervention,
                COUNT(CASE WHEN has_escalation THEN 1 END)               AS escalades,
                COUNT(CASE WHEN has_rag_relaunch THEN 1 END)             AS rag_relaunch,
                COUNT(CASE WHEN has_kb_signal THEN 1 END)                AS kb_signal,
                COUNT(CASE WHEN has_training THEN 1 END)                 AS formation,
                COUNT(*)                                                  AS total
            FROM workforce_decisions
        """)
        r = rows[0] if rows else {}
        return {
            "optimal": int(r.get("optimal") or 0),
            "intervention": int(r.get("intervention") or 0),
            "total": int(r.get("total") or 0),
            "actions": [
                {"type": "Escalade humain", "nb": int(r.get("escalades") or 0)},
                {"type": "Relancer RAG",    "nb": int(r.get("rag_relaunch") or 0)},
                {"type": "Signaler KB",     "nb": int(r.get("kb_signal") or 0)},
                {"type": "Formation",       "nb": int(r.get("formation") or 0)},
            ],
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── ALERTES RÉCENTES ──────────────────────────────────────────────────────────
@router.get("/alerts")
def get_alerts(limit: int = 10):
    if not is_configured():
        return []
    try:
        rows = _pg("""
            SELECT * FROM v_escalation_log LIMIT %s
        """, [min(limit, 50)])
        return [
            {
                "conversationId": r["conversation_id"],
                "createdAt": str(r["created_at"]),
                "profile": r["profile"],
                "topic": r["topic"],
                "urgency": r["urgency"],
                "clientName": r["client_name"],
                "globalScore": int(r["global_score"]) if r["global_score"] else None,
                "priority": r["priority"],
                "alerts": r["alerts"],
                "requiresHumanReview": bool(r["requires_human_review"]),
                "problems": r["problems"],
                "actionTypes": r["action_types"],
            }
            for r in rows
        ]
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── CONVERSATIONS RÉCENTES ────────────────────────────────────────────────────
@router.get("/conversations")
def get_conversations(limit: int = 20, profile: Optional[str] = None, topic: Optional[str] = None):
    if not is_configured():
        return []
    try:
        where = ["1=1"]
        params: list = []
        if profile:
            where.append("c.profile = %s")
            params.append(profile)
        if topic:
            where.append("c.topic ILIKE %s")
            params.append(f"%{topic}%")
        params.append(min(limit, 100))
        rows = _pg(f"""
            SELECT
                c.id, c.created_at, c.profile, c.topic, c.urgency,
                c.client_name, c.client_age, c.client_city, c.completed_turns,
                c.total_latency_ms, c.advisor_model,
                q.global_score, q.priority, q.requires_human_review,
                w.status AS workforce_status, w.action_types, w.has_escalation
            FROM sim_conversations c
            LEFT JOIN quality_evaluations q ON q.conversation_id = c.id
            LEFT JOIN workforce_decisions  w ON w.conversation_id = c.id
            WHERE {' AND '.join(where)}
            ORDER BY c.created_at DESC
            LIMIT %s
        """, params)
        return [
            {
                "id": r["id"],
                "createdAt": str(r["created_at"]),
                "profile": r["profile"],
                "topic": r["topic"],
                "urgency": r["urgency"],
                "clientName": r["client_name"],
                "clientAge": r["client_age"],
                "clientCity": r["client_city"],
                "completedTurns": r["completed_turns"],
                "totalLatencyMs": r["total_latency_ms"],
                "advisorModel": r["advisor_model"],
                "globalScore": int(r["global_score"]) if r["global_score"] else None,
                "priority": r["priority"],
                "requiresHumanReview": bool(r["requires_human_review"]) if r["requires_human_review"] is not None else False,
                "workforceStatus": r["workforce_status"],
                "actionTypes": r["action_types"],
                "hasEscalation": bool(r["has_escalation"]) if r["has_escalation"] is not None else False,
            }
            for r in rows
        ]
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── ANALYSE PAR THÉMATIQUE ────────────────────────────────────────────────────
@router.get("/topics")
def get_topics():
    if not is_configured():
        return []
    try:
        rows = _pg("SELECT * FROM v_topic_analysis ORDER BY nb_conversations DESC")
        return [
            {
                "topic": r["topic"],
                "nb": int(r["nb_conversations"] or 0),
                "score": float(r["avg_quality_score"]) if r["avg_quality_score"] else None,
                "pertinence": float(r["avg_pertinence"]) if r["avg_pertinence"] else None,
                "escaladeRate": float(r["escalation_rate_pct"]) if r["escalation_rate_pct"] else None,
                "nbHighRisk": int(r["nb_high_risk"] or 0),
            }
            for r in rows
        ]
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
