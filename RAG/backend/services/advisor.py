"""Logique métier du Conseiller : instance unique de l'agent RAG, conversion vers les schémas de l'API."""
import re
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel

from backend.core import agent as ag
from backend.schemas import (AdvisorRequest, AdvisorResponse, Product, ProductContext, Source, ToolStep)

# Le front connaît "heureux" ; l'agent ne l'avait pas dans PROFILE_STYLES
ag.PROFILE_STYLES.setdefault(
    "heureux",
    "Client heureux : ton chaleureux et enthousiaste, remercie en une phrase, reste concis, "
    "ne propose que ce qui figure dans le contexte.",
)

# Thématiques du front -> mots-clés compris par agent.topic_modules()
TOPIC_ALIASES = {
    "auto": None,  # aucune thématique forcée : l'agent choisit lui-même ses outils
    "fidelite": "offre fidelite promo",
    "technique": "panne acces",
    "resiliation": "resiliation abonnement",
    "soins": "paramedical produit",
    "bebe_maman": "paramedical produit",
    "bien_etre": "paramedical produit",
    "precautions": "precaution paramedical",
    "choix": "achat produit",
    "symptome": "symptome paramedical",
}

MODULE_LABELS = {
    "facturation_frais": "Facturation & Frais",
    "remboursement_avoir": "Remboursement & Avoir",
    "securite_alerte_sms": "Sécurité & Alerte SMS",
    "offres_fiabilite": "Offres & Fiabilité",
    "panne_acces_services": "Panne & Accès",
    "resiliation_contrat": "Résiliation",
    "conseil_paramedical": "Conseil paramédical",
    "guide_achat": "Guide d'achat",
}


AGENT: Optional[ag.PharmaAgent] = None
FULL_DESC: dict = {}  # url produit -> description complète (l'agent ne garde que 300 caractères)


def init_agent() -> None:
    """Charge catalogue + index ChromaDB une seule fois (appelé au démarrage du serveur)."""
    global AGENT
    AGENT = ag.PharmaAgent(debug=False)
    FULL_DESC.update({r.url: re.sub(r"\s+", " ", r.description)[:1500] for r in AGENT.catalog.itertuples()})


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", ag.strip_accents((s or "").lower())).strip("-")[:48]


def to_product(p: dict) -> Product:
    return Product(name=p["nom"], brand=p.get("marque", ""), price=p.get("prix", ""), inStock=bool(p.get("en_stock")),
                   url=p.get("lien", ""), description=p.get("description", ""),
                   fullDescription=FULL_DESC.get(p.get("lien", ""), p.get("description", "")), score=p.get("score", 0))


def to_response(raw: dict, latency_ms: int) -> AdvisorResponse:
    ctx = raw.get("context") or {}
    svc = ctx.get("CONTEXTE_SERVICE") or {}
    sources = [
        Source(id=f"{d.get('module')}:{slug(d.get('titre'))}", title=d.get("titre") or "Document",
               score=d.get("score", 0), module=d.get("module"), snippet=(d.get("contenu") or "")[:240],
               illustrative=bool(d.get("illustratif")), expired=bool(d.get("expire")))
        for d in svc.get("documents", [])
    ]
    prod = ctx.get("CONTEXTE_PRODUITS")
    products = None
    if prod:
        products = ProductContext(
            scenario=prod["scenario"], budgetMax=prod.get("budget_max_tnd"),
            inStock=[to_product(p) for p in prod["produits_en_stock"]],
            outOfStock=[to_product(p) for p in prod["produits_en_rupture"]])
    med = ctx.get("CONTEXTE_MEDICAL") or {}
    return AdvisorResponse(
        answer=raw["answer"], intent=raw.get("intent", "chitchat"), sources=sources, latencyMs=latency_ms,
        model=raw.get("model"), mode=raw.get("mode"), urgent=bool(raw.get("urgent")),
        modules=raw.get("modules", []), specialists=med.get("specialistes_recommandes", []),
        products=products, steps=[ToolStep(**s) for s in raw.get("steps", [])])


def run_advisor(req: AdvisorRequest) -> AdvisorResponse:
    history = [("Utilisateur" if t.role == "client" else "Assistant", t.content) for t in req.history]
    topic = TOPIC_ALIASES[req.topic] if req.topic in TOPIC_ALIASES else req.topic
    t0 = time.perf_counter()
    try:
        raw = AGENT.chat(req.message, history, profile=req.profile, topic=topic, rag=req.rag)
    except (RuntimeError, SystemExit) as e:  # aucun modèle dispo / clé API manquante
        raise HTTPException(503, str(e))
    return to_response(raw, int((time.perf_counter() - t0) * 1000))


def dump(model: BaseModel) -> dict:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()



def front_fields(res: AdvisorResponse, rag: bool, count: int = 1, exchanges: Optional[list] = None) -> AdvisorResponse:
    """Champs attendus par la page Conseiller du front, en plus de la réponse du RAG."""
    res.ragActive = rag
    res.generatedAt = datetime.now(timezone.utc).isoformat()
    res.confidence = max((s.score for s in res.sources), default=None)
    res.messageCount = count
    res.isConversation = count > 1
    res.conversationExchanges = exchanges or []
    return res



def quality_reference(message: str) -> dict:
    """Faits du RAG liés à la question du client, pour l'Analyste Qualité (recherche vectorielle seule, sans LLM)."""
    parts, sources = [], []
    docs = AGENT.search_services(message, list(AGENT.services))["documents"]
    for d in docs:
        parts.append(f"[{d.get('module')}] {d.get('titre')}: {d.get('contenu') or ''}")
        sources.append({"id": f"{d.get('module')}:{slug(d.get('titre'))}", "title": d.get("titre"), "score": d.get("score", 0)})
    prod = AGENT.search_products(message)
    for p in prod["produits_en_stock"] + prod["produits_en_rupture"]:
        parts.append(f"[produit] {p['nom']} ({p['marque']}), {p['prix']}, {'en stock' if p['en_stock'] else 'en rupture'}: {p['description']}")
        sources.append({"id": p["lien"], "title": p["nom"], "score": p.get("score", 0)})
    return {"text": "\n".join(parts), "sources": sources}
