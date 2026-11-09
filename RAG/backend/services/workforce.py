"""Workforce Manager : transforme un rapport de l'Analyste Qualité (+ KPI) en problèmes et plan d'actions.

Règles déterministes et traçables, sans LLM : chaque action cite le signal qui l'a déclenchée.
"""
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

from backend.quality import router as quality

SCORE_TARGET = 75      # seuil cible du score global (/100)
CRITERION_TARGET = 75  # seuil cible empathie / ancrage documentaire
ESCALATION_ALERT = 15  # taux d'escalade (%) au-delà duquel on alerte


def _action(type_: str, description: str, priority: str, responsible: str) -> dict:
    return {"type": type_, "description": description, "priority": priority, "responsible": responsible}


def decide(evaluation: dict[str, Any], profile: str, kpi: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    score = evaluation.get("globalScore")
    score = 80 if score is None else score
    criteria = evaluation.get("criteria") or {}
    empathy, grounding = criteria.get("empathie"), criteria.get("groundedness")  # None = non vérifié
    lora = evaluation.get("loraRisk") or {}
    critical = (evaluation.get("priority") == "critique" or bool(evaluation.get("requiresHumanReview"))
                or lora.get("label") == "CRITIQUE")

    problems: list[str] = []
    actions: list[dict] = []

    if critical:
        problems.append("Signal de sécurité : revue humaine requise (alerte critique de l'Analyste Qualité)")
        problems.extend(evaluation.get("alerts") or [])
        actions.append(_action("escalade_humain", "Suspendre la réponse et la faire valider par un superviseur avant tout envoi.",
                               "haute", "Superviseur Équipe N2"))
    if score < SCORE_TARGET:
        problems.append(f"Score global insuffisant ({score}/100) en dessous du seuil cible ({SCORE_TARGET})")
        if not critical:
            actions.append(_action("escalade_humain", "Transférer le dossier vers un conseiller senior niveau 2 pour prise en charge personnalisée.",
                                   "haute", "Superviseur Équipe N2"))
    pertinence = criteria.get("pertinence")
    if pertinence is not None and pertinence < 60:
        problems.append(f"Réponse peu pertinente ({pertinence}/100)")
        actions.append(_action("relancer_rag", "Relancer la recherche RAG avec une reformulation de la demande du client.",
                               "moyenne", "Responsable RAG"))
    conformite = criteria.get("conformite")
    if conformite is not None and conformite < 40:
        problems.append(f"Conformité faible ({conformite}/100)")
        actions.append(_action("ajuster_reponse", "Renforcer les garde-fous du prompt (secrets, doses, données de santé).",
                               "haute", "Lead Prompt Engineer"))
    if empathy is not None and empathy < CRITERION_TARGET:
        problems.append(f"Déficit d'empathie détecté ({empathy}/100) face à un profil {profile}")
        actions.append(_action("ajuster_reponse", f"Ajuster les consignes de tonalité (prompt système) pour le persona {profile}.",
                               "moyenne", "Lead Prompt Engineer"))
    if grounding is not None and grounding < CRITERION_TARGET:
        problems.append(f"Ancrage documentaire insuffisant ({grounding}/100)")
        actions.append(_action("signaler_kb", "Compléter et mettre à jour la fiche documentaire correspondante dans la base de connaissances.",
                               "moyenne", "Responsable Base Documentaire"))
    if kpi and (kpi.get("tauxEscalade") or 0) > ESCALATION_ALERT:
        problems.append(f"Taux d'escalade global élevé ({kpi['tauxEscalade']}%)")

    actions.append(_action("formation", "Programmer un module de micro-learning de 15 min sur la désescalade émotionnelle.",
                           "basse", "RH & Formation"))

    needs_help = critical or score < SCORE_TARGET
    return {
        "agent": "Workforce Manager Agent",
        "auditScore": score,
        "status": "INTERVENTION_REQUISE" if needs_help else "OPTIMAL",
        "problems": problems,
        "actions": actions,
        "workforceSummary": {
            "staffingImpact": "+1 escalade vers N2" if needs_help else "Traitement 100% autonome",
            "trainingModuleSuggested": ("Module Empathie & Posture relationnelle" if empathy is not None and empathy < CRITERION_TARGET
                                        else "Veille réglementaire continue"),
            "kbUpdateRequired": grounding is not None and grounding < CRITERION_TARGET,
        },
        "decidedAt": datetime.now(timezone.utc).isoformat(),
    }


def compute_kpi() -> dict[str, Any]:
    """KPI calculés sur les évaluations de l'Analyste Qualité enregistrées (SQLite)."""
    reports: list[dict] = []
    if quality.DB_PATH.exists():
        with sqlite3.connect(quality.DB_PATH) as conn:
            try:
                reports = [json.loads(r[0]) for r in conn.execute("SELECT report_json FROM evaluations")]
            except sqlite3.OperationalError:  # table pas encore créée
                pass
    n = len(reports)
    if not n:
        return {"qualiteReponses": None, "tauxResolution": None, "tempsTraitementSec": None, "tauxEscalade": None,
                "satisfactionClient": None, "performanceParProfil": [], "evaluations": 0}
    escalated = sum(bool(r.get("requiresHumanReview")) for r in reports)
    resolved = sum(r["globalScore"] >= SCORE_TARGET and not r.get("requiresHumanReview") for r in reports)
    by_profile: dict[str, list[int]] = {}
    for r in reports:
        by_profile.setdefault(r.get("profile") or "non_precise", []).append(r["globalScore"])
    return {
        "qualiteReponses": round(sum(r["globalScore"] for r in reports) / n, 1),
        "tauxResolution": round(100 * resolved / n, 1),   # proxy : score >= seuil et sans revue humaine
        "tauxEscalade": round(100 * escalated / n, 1),    # revue humaine requise
        "tempsTraitementSec": None,                       # non mesuré par l'Analyste Qualité
        "satisfactionClient": None,                       # pas de donnée client réelle
        "performanceParProfil": [{"profile": p, "score": round(sum(v) / len(v)), "count": len(v)}
                                 for p, v in sorted(by_profile.items())],
        "evaluations": n,
    }
