# Intégration avec le front et les vrais agents

## 1. Où on en est

| Élément | État |
|---|---|
| Front (`dt-front`) | Par défaut en **données factices** (`VITE_USE_MOCK=true`). En mode réel, il appelle `/api/...`, que Vite redirige vers `http://localhost:8000`. |
| Workforce Manager (cet agent) | **Compatible avec la page du front telle qu'elle est.** Testé le 22/10/2026 : vrai front en mode réel + cette API → la page affiche statut, problèmes, actions, responsables et synthèse d'impact. |
| Autres agents | À brancher (voir section 3). |
| `/simulations`, `/conversations`, `/profiles`, `/kpi` global | N'appartiennent à aucun agent : c'est le rôle d'un **orchestrateur** (section 3). |

## 2. Ce que le Workforce Manager accepte et renvoie

**Requête** `POST /api/agents/workforce-manager`. Tous les champs sauf `evaluation` sont facultatifs :

```json
{
  "evaluation": { "globalScore": 62, "criteria": { "empathie": 55, "conformite": 40 } },
  "request":    { "profile": "mecontent", "message": "...", "intent": "...", "entities": { "type_demande": "sante" } },
  "kpi":        { "tauxEscalade": 8.5, "qualiteReponses": 82.4 },
  "type_demande": "sante"
}
```

**Type de demande**, dans cet ordre de priorité :
1. `type_demande` ;
2. `request.entities.type_demande` ;
3. mots-clés de `request.intent`, puis de `request.message` ;
4. à défaut, la demande est traitée comme **santé**, par précaution.

L'en-tête de réponse `X-Type-Demande-Source` indique d'où vient le type retenu.

**Réponse** : le contrat (`problems`, `actions`), plus les champs lus par le front : `actions[].responsible`, `status`, `auditScore`, `typeDemande`, `workforceSummary`, `agent` et `decidedAt`.
`?strict=true` renvoie **exactement** le contrat v1.

**Proposition de contrat pour l'équipe** : `docs/openapi_workforce_manager_v2.yaml` (uniquement des ajouts optionnels, donc rétrocompatible).

## 3. Architecture cible avec les vrais agents

Chaque membre garde **son agent dans son propre service**, et un **orchestrateur** unique sert le front.

```
 Front (Vite :5173)
      │  /api/*   (proxy Vite, déjà configuré vers :8000)
      ▼
 Orchestrateur (:8000) ── /simulations, /conversations, /profiles, /kpi, /knowledge-base
      │  relaie /agents/* et enchaîne les agents pour /simulations
      ├──▶ Client Simulator   (:8001)  POST /api/agents/client-simulator
      ├──▶ Customer Advisor   (:8002)  POST /api/agents/customer-advisor
      ├──▶ Quality Analyst    (:8003)  POST /api/agents/quality-analyst
      └──▶ Workforce Manager  (:8004)  POST /api/agents/workforce-manager   ← cet agent
```

Lancer cet agent sur son port :

```powershell
python -m uvicorn workforce_manager.api.main:app --port 8004
```

**Ce que fait l'orchestrateur pour `POST /simulations`** (la chaîne complète du Swagger) :

```python
# Esquisse FastAPI + httpx (à placer dans le service orchestrateur, pas dans un agent)
AGENTS = {"client": "http://localhost:8001", "advisor": "http://localhost:8002",
          "quality": "http://localhost:8003", "workforce": "http://localhost:8004"}

@app.post("/api/simulations", status_code=201)
async def simulation(corps: dict):
    async with httpx.AsyncClient(timeout=60) as http:
        demande = corps if corps.get("message") else (await http.post(
            f"{AGENTS['client']}/api/agents/client-simulator", json=corps)).json()
        reponse = (await http.post(f"{AGENTS['advisor']}/api/agents/customer-advisor", json=demande)).json()
        evaluation = (await http.post(f"{AGENTS['quality']}/api/agents/quality-analyst",
                                      json={"request": demande, "response": reponse})).json()
        decision = (await http.post(f"{AGENTS['workforce']}/api/agents/workforce-manager",
                                    json={"evaluation": evaluation, "request": demande})).json()
    resultat = {"id": str(uuid4()), "createdAt": datetime.now(timezone.utc).isoformat(),
                "request": demande, "response": reponse, "evaluation": evaluation, "decision": decision}
    HISTORIQUE.append(resultat)          # sert ensuite /simulations, /conversations et /kpi
    return resultat
```

Point clé : l'orchestrateur transmet `request` au Workforce Manager. C'est ce qui permet de reconnaître une demande santé ou une urgence, au lieu d'appliquer la précaution par défaut.

**Variante sans orchestrateur** (pour tester les pages unitaires seulement) : dans `vite.config.js`, un proxy par agent, du plus précis au plus général :

```js
proxy: {
  '/api/agents/workforce-manager': { target: 'http://localhost:8004', changeOrigin: true },
  '/api/agents/quality-analyst':   { target: 'http://localhost:8003', changeOrigin: true },
  '/api/agents/customer-advisor':  { target: 'http://localhost:8002', changeOrigin: true },
  '/api/agents/client-simulator':  { target: 'http://localhost:8001', changeOrigin: true },
  '/api':                          { target: 'http://localhost:8000', changeOrigin: true },
},
```

## 4. Ce que le Workforce Manager attend des autres agents

| De qui | Quoi | Pourquoi |
|---|---|---|
| **Quality Analyst** | Les 6 critères notés **sur 100**, comme `globalScore` | Les seuils (60, 70, 40) supposent cette échelle. **À confirmer** : si l'échelle est 0-5 ou 0-10, il faut prévenir, car il suffit d'une conversion à l'entrée. |
| **Quality Analyst** | Les 6 critères présents | Un critère absent est signalé. Une conformité absente sur une demande santé déclenche une vérification par le pharmacien. |
| **Client Simulator** | `entities.type_demande` (`standard`, `sante` ou `urgence`) si possible | C'est la source la plus fiable du type de demande. |
| **Orchestrateur** | `{evaluation, request}` dans l'appel | Voir section 3. |

## 5. Petites demandes à l'équipe front (non bloquantes)

1. **`WorkforceManagerPage.jsx` envoie seulement 3 critères** (score, empathie, groundedness). Sans la conformité, l'agent applique la précaution santé et demande une vérification par le pharmacien à chaque fois. Quand la page est ouverte depuis le Quality Analyst, il vaudrait mieux envoyer l'évaluation complète (`prefilled.evaluation`) et la demande complète (`prefilled.request`).
2. Au chargement, `/api/conversations` et `/api/kpi` renvoient 404 tant que l'orchestrateur n'existe pas. Dans `App.jsx`, l'erreur n'est pas capturée (« Uncaught (in promise) »). Il suffit d'ajouter un `.catch()`.
3. Facultatif : afficher `typeDemande`, qui fait partie de la réponse.

## 6. Tester l'intégration (pas à pas)

```powershell
# Terminal 1 – le Workforce Manager (sans consommer le quota Gemini pendant les tests)
$env:WM_LLM = "off"
python -m uvicorn workforce_manager.api.main:app --port 8000

# Terminal 2 – le front en mode réel (aucun fichier modifié)
cd ..\dt-front
$env:VITE_USE_MOCK = "false"
npm run dev
```

Ouvre ensuite http://localhost:5173/agents/workforce-manager, choisis un scénario et clique sur « Déclencher les décisions managériales ».

- `WM_LLM=off` : textes fixes, aucun appel à Gemini (le quota gratuit est de 20 requêtes par jour). Retire la variable pour retrouver les explications rédigées par Gemini.
- Avec l'orchestrateur, lance plutôt cet agent sur le port 8004 (section 3).

## 7. Et le niveau macro (RL) ?

Les vrais agents produisent des **conversations**. Le pilotage RL agit sur le **jumeau numérique** du centre : files d'attente, conseillers, journées. C'est précisément le rôle du Digital Twin, qui permet de tester une stratégie de pilotage avant de l'appliquer.

Les deux niveaux se branchent ainsi :
- **aujourd'hui** : l'endpoint `simulate-day` (`docs/openapi_simulate_day.yaml`) permet à une page « Pilotage » de rejouer une journée avec l'agent ;
- **ensuite** : les évaluations réelles collectées par l'orchestrateur (`/conversations`) pourront remplacer les 200 évaluations simulées (`data/mock_evaluations.json`). Le simulateur aura alors la qualité réelle de vos agents, et l'agent RL sera réentraîné dessus.
