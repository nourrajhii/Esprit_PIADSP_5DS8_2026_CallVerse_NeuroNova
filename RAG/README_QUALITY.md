# Backend unique (RAG + Simulateur client + Analyste Qualité)

Un seul serveur, un seul lancement :

```powershell
cd RAG
.\run.ps1          # uvicorn server:app --port 8000
```

Le front (`dt-front`, proxy Vite `/api` → `localhost:8000`) n'a besoin d'aucun autre port.

## Structure

```
RAG/
  server.py              point d'entrée (uvicorn server:app)
  .env  data/  .cache/   configuration, données, index vectoriels
  backend/
    main.py              création de l'app : CORS, routeurs, format d'erreur, démarrage
    settings.py          chemins (ROOT, CLIENT_DIR), .env, CORS_ORIGINS
    schemas.py           modèles Pydantic des requêtes/réponses
    routes/              advisor, simulation, knowledge_base, health
    services/advisor.py  agent RAG unique + conversion vers les schémas
    core/                agent.py (RAG/LLM), orchestrator.py (client <-> conseiller), db.py (PostgreSQL)
    quality/             Analyste Qualité : router, qa_judge, qa_lora, models/ (adaptateur LoRA)
  tests/                 pytest (Analyste Qualité)
```

L'agent RAG en ligne de commande : `python -m backend.core.agent`.

## Analyste Qualité (`backend/quality/`)

Routeur FastAPI monté par `server.py`. À chaque évaluation, les faits du RAG (services + produits liés à la
question du client) sont retrouvés par recherche vectorielle et transmis au juge Gemini (`ragReference` dans le rapport).

| Route | Rôle |
|---|---|
| `POST /api/agents/workforce-manager` | Agent 4 : problèmes + plan d actions depuis le rapport Qualité |
| `GET /api/kpi` | KPI calculés sur les évaluations Qualité enregistrées |
| `POST /api/agents/quality-analyst` (= `/api/quality/evaluate`) | Score Gemini + règles de sécurité + RAG |
| `POST /api/quality/lora/check` | Qwen2.5-0.5B + LoRA local (CRITIQUE / NON_CRITIQUE) |
| `POST /api/quality/judge/evaluate` | Second juge LLM, rubrique 0-4 |
| `GET /api/quality/health`, `/kpis`, `/evaluations`, `/lora/experiment`, `/judge/health` | Suivi |

Variables `.env` : `GEMINI_API_KEY`, `GEMINI_MODEL`, `QA_JUDGE_MODEL`, `QA_LORA_ENABLED` (1 pour activer, après
`pip install -r requirements-lora.txt`), `QA_LORA_AUTO`, `CORS_ORIGINS`.

Tests : `python -m pytest -q`.

## Simulation globale

`POST /api/simulations` (1 échange) et `POST /api/simulations/conversation` (1 à 5 messages) enchaînent :
Client Simulator → Conseiller RAG → Analyste Qualité (par tour) → Workforce Manager, et renvoient le
`SimulationResult` du front (`request`, `response`, `exchanges`, `evaluation`, `decision`).
L'historique (`GET /api/conversations`, `/api/simulations`, `/api/simulations/{id}`) est dans `.cache/simulations.json` ;
la conversation est aussi enregistrée dans PostgreSQL si `DATABASE_URL` est définie. La conversation menée page par page
(`/api/simulations/conversation/save`) passe par la même évaluation.
