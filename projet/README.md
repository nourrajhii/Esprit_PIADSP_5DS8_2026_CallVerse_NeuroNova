# Twinly – Front-end du Digital Twin (Centre de Relation Client)

Front React (Vite) + contrat d'API Swagger/OpenAPI.

## Lancer

```bash
npm install
cp .env.example .env     # VITE_USE_MOCK=true → fonctionne sans backend
npm run dev              # http://localhost:5173
```

Pour brancher le vrai backend : `VITE_USE_MOCK=false` dans `.env`. Les appels `/api/*`
sont redirigés vers `http://localhost:8000` (voir `vite.config.js`).

## Structure

```
swagger/openapi.yaml        Contrat d'API (à partager avec l'équipe back-end)
public/openapi.yaml         Copie servie à la page /api-docs
src/api/client.js           Appels HTTP (1 fonction = 1 endpoint du swagger)
src/api/mock.js             Données simulées conformes au swagger
src/components/             Sidebar, Topbar, Composer, SimulationResult
src/pages/Simulation.jsx    Lancer un scénario (client → conseiller → qualité → workforce)
src/pages/Dashboard.jsx     KPI temps réel + performance par profil
src/pages/Historique.jsx    Historique des conversations
src/pages/ApiDocs.jsx       Swagger UI intégré
```

## Endpoints (résumé)

| Méthode | Route | Agent / usage |
|---|---|---|
| GET | /profiles | Profils clients |
| POST | /simulations | Workflow complet (4 agents) |
| GET | /simulations, /simulations/{id} | Liste / détail |
| POST | /agents/client-simulator | Agent 1 |
| POST | /agents/customer-advisor | Agent 2 (RAG) |
| POST | /agents/quality-analyst | Agent 3 |
| POST | /agents/workforce-manager | Agent 4 |
| GET | /conversations | Historique |
| GET | /kpi | KPI temps réel |
| GET/POST | /knowledge-base/documents | Base de connaissances |

Si vous modifiez `swagger/openapi.yaml`, recopiez-le dans `public/`.
