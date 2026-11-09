# CallVerse — Digital Twin d'un centre de contact

Projet de l'équipe *Neuro Nova* (Esprit). CallVerse rejoue des conversations sensibles d'une parapharmacie en ligne (PharmaShop) dans un environnement simulé, les évalue et décide d'actions correctives. Méthodologie : Design Thinking.

Quatre agents IA tournent dans *un seul serveur FastAPI* (port 8000), piloté par un front React :

| # | Agent | Rôle | Techniques |
|---|-------|------|------------|
| 1 | *Client Simulator* | Joue 8 profils de clients (calme, impatient, nerveux...) | Qwen2.5-3B fine-tuné (Ollama), prompting par persona |
| 2 | *Customer Advisor* | Répond à partir de documents | RAG : routeur + ChromaDB + MiniLM, LLM Groq ou Ollama |
| 3 | *Quality Analyst* | Note chaque réponse, détecte les risques | Juge Gemini, règles de sécurité, classifieur Qwen-LoRA |
| 4 | *Workforce Manager* | Transforme les scores en plan d'actions | Règles déterministes (sans LLM) |

Chaîne d'une simulation globale : Client → Conseiller (RAG) → Analyste Qualité → Workforce Manager → historique + base de données.

---

## 1. Prérequis

| Outil | Version | Usage |
|-------|---------|-------|
| Python | 3.10 ou plus | backend |
| Node.js | 18 ou plus | front React |
| [Ollama](https://ollama.com) | récent | modèles locaux (client simulé, conseiller local) |
| Clé API Gemini | — | juge de l'Analyste Qualité (obligatoire pour noter) |
| Clé API Groq | — | facultatif : LLM du conseiller dans le cloud |
| PostgreSQL | 14 ou plus | facultatif : enregistrement des conversations / Power BI |

Les commandes ci-dessous sont pour **Windows PowerShell**.


---

## 2. Installation

### 2.1 Backend

cd RAG
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Classifieur de risque LoRA (facultatif, lourd : PyTorch) :

.\.venv\Scripts\python.exe -m pip install -r requirements-lora.txt

### 2.2 Configuration (RAG/.env)

copy .env.example .env

Puis ouvrir RAG/.env et renseigner au minimum GEMINI_API_KEY. *Ne jamais committer ce fichier* (il est dans .gitignore).

| Variable | Rôle | Exemple |
|----------|------|---------|
| LLM_PROVIDER | LLM du conseiller : ollama, groq ou gemini | ollama |
| GROQ_API_KEY, GROQ_MODEL | si groq | openai/gpt-oss-120b |
| LLM_CHAIN, ROUTER_CHAIN | chaîne de modèles de secours, format fournisseur:modèle séparés par des virgules (facultatif) | groq:openai/gpt-oss-120b,gemini:gemini-2.5-flash |
| OLLAMA_LLM_MODEL | modèle local du conseiller | qwen2.5:7b |
| OLLAMA_MODEL | modèle du Client Simulator, 1er message | qwen-client-v2 |
| OLLAMA_MODEL_SUITE | modèle du client, messages 2 à 5 | qwen2.5:7b |
| AGENTIC | 0 = pipeline routeur → RAG (recommandé avec un 7B local) | 0 |
| GEMINI_API_KEY | clé du juge Gemini (Analyste Qualité) | — |
| QA_JUDGE_MODEL | modèle du juge | voir .env.example |
| QA_LORA_ENABLED | 1 pour activer le classifieur LoRA | 0 |
| DATABASE_URL | PostgreSQL (facultatif) | postgresql://user:pass@localhost:5432/callverse |
| CORS_ORIGINS | origines du front autorisées | http://localhost:5173 |

### 2.3 Modèles Ollama

ollama pull qwen2.5:7b

Modèle client fine-tuné (le fichier .gguf pèse environ 1,8 Go et n'est pas versionné : à récupérer auprès de l'équipe). Ouvrir client/modele/Modelfile, corriger la ligne FROM avec le chemin réel du .gguf, puis :

ollama create qwen-client-v2 -f client/modele/Modelfile

Sans ce modèle, mettre OLLAMA_MODEL=qwen2.5:7b dans .env : le simulateur fonctionne avec le modèle de base.

### 2.4 Base PostgreSQL (facultatif)

Créer une base vide puis renseigner DATABASE_URL. Les tables (sim_clients, sim_conversations, sim_turns, sim_sources) et la vue v_powerbi_turns sont *créées automatiquement* au démarrage. Sans DATABASE_URL, tout fonctionne : seul l'enregistrement PostgreSQL est désactivé. L'historique est gardé dans RAG/.cache/simulations.json et les évaluations qualité dans SQLite.

### 2.5 Front end

cd dt-front
npm install
copy .env.example .env     # puis mettre VITE_USE_MOCK=false pour utiliser le vrai backend

---

## 3. Exécution

Trois terminaux.

*Terminal 1 — Ollama* (s'il n'est pas déjà lancé en service) :

ollama serve

*Terminal 2 — Backend* (toujours depuis le dossier RAG) :

cd RAG
.\.venv\Scripts\python.exe -m uvicorn server:app --port 8000

ou .\run.ps1 (même chose avec rechargement automatique). Au premier lancement, le modèle d'embeddings est téléchargé et l'index ChromaDB est construit dans RAG/.cache/ : compter quelques minutes.

*Terminal 3 — Front* :

cd dt-front
npm run dev

| Adresse | Contenu |
|---------|---------|
| http://localhost:5173 | application web |
| http://localhost:8000/docs | documentation Swagger de l'API |
| http://localhost:8000/api/health | état du backend |
| http://localhost:8000/api/quality/health | état de l'Analyste Qualité |

Le front appelle /api/... ; Vite redirige vers le port 8000 (voir dt-front/vite.config.js).

### Tests

cd RAG
.\.venv\Scripts\python.exe -m pytest

41 tests (Analyste Qualité, Workforce Manager, simulation globale). Ils utilisent des fournisseurs simulés : aucune clé API n'est nécessaire.

---

## 4. Structure du projet

.
├── RAG/                        Backend unique (FastAPI) : à lancer depuis ce dossier
│   ├── server.py               point d'entrée : uvicorn server:app
│   ├── run.ps1                 lance le serveur avec rechargement
│   ├── requirements.txt        dépendances (+ requirements-lora.txt, facultatif)
│   ├── .env.example            modèle de configuration
│   ├── data/                   catalogue produits, maladies, modules de service (CSV)
│   ├── .cache/                 index vectoriel, historique des simulations (généré)
│   ├── backend/
│   │   ├── main.py             application, routeurs, CORS, gestion d'erreurs
│   │   ├── settings.py         chemins et variables d'environnement
│   │   ├── schemas.py          modèles Pydantic des requêtes et réponses
│   │   ├── routes/             une route par agent + historique, base de connaissances, santé
│   │   ├── services/           logique métier : advisor, simulation, workforce, history
│   │   ├── core/               agent.py (RAG), orchestrator.py (client ↔ conseiller), db.py (PostgreSQL)
│   │   └── quality/            Analyste Qualité : juge Gemini, classifieur LoRA, modèles
│   └── tests/                  tests pytest
│
├── client/                     Client Simulator
│   ├── app/                    profils, prompts, génération des messages (Ollama)
│   ├── evaluation/             scripts : construire, nettoyer, évaluer le jeu de profils
│   ├── eval/results/           résultats d'évaluation des modèles clients
│   └── modele/                 Modelfile Ollama (le .gguf n'est pas versionné)
│
├── dt-front/                   Front React (Vite)
│   ├── src/pages/              Simulation globale, Tableau de bord, Historique, API, pages des agents
│   ├── src/api/                client HTTP et mode démo (mock)
│   └── swagger/                contrat OpenAPI
│
├── projet/                     version autonome d'origine de l'Analyste Qualité (référence)
├── workforce_manager/          version autonome d'origine du Workforce Manager (référence)
├── rapport_callverse.tex       rapport du projet (LaTeX, anglais)
└── architecture.png            schéma d'architecture globale

L'Analyste Qualité et le Workforce Manager vivent désormais dans RAG/backend/ ; projet/ et workforce_manager/ ne servent plus à l'exécution.

---

## 5. Routes principales de l'API

| Route | Rôle |
|-------|------|
| POST /api/agents/client-simulator | message d'un client virtuel |
| POST /api/agents/customer-advisor | réponse du conseiller (RAG) |
| POST /api/agents/quality-analyst | évaluation d'une réponse |
| POST /api/agents/workforce-manager | problèmes et plan d'actions |
| POST /api/simulations et /api/simulations/conversation | simulation globale (1 à 5 messages) |
| GET /api/simulations, /api/simulations/{id} | historique |
| GET /api/kpi | indicateurs calculés sur les évaluations |
| GET /api/health, /api/quality/health | état des services |

Liste complète : http://localhost:8000/docs.

---

## 6. Dépannage

| Problème | Solution |
|----------|----------|
| Could not import module "server" | lancer uvicorn **depuis le dossier RAG**, pas depuis la racine |
| Erreur 503 du juge Gemini | indisponibilité temporaire du fournisseur : réessayer ; aucun score n'est inventé |
| GEMINI_API_KEY absente : juge non exécuté | renseigner la clé dans RAG/.env |
| Réponses très lentes | chaque tour appelle un LLM local puis le juge : utiliser LLM_PROVIDER=groq pour le conseiller |
| Front sans données réelles | vérifier VITE_USE_MOCK=false dans dt-front/.env et que le backend tourne |
| qwen-client-v2 introuvable | créer le modèle (section 2.3) ou utiliser OLLAMA_MODEL=qwen2.5:7b |

---

## 7. Limites connues

- Les scores du juge ne sont pas calibrés sur des annotations humaines ; exactitude et ancrage documentaire ne sont pas vérifiés de façon indépendante (affichés « Non vérifié »).
- Le classifieur LoRA a été évalué sur 14 exemples synthétiques : résultats exploratoires, non validés pour un usage médical.
- Le client simulé est un modèle de langage ; aucun test n'a encore été fait avec de vrais conseillers ou clients.
- Le système n'est pas certifié pour un usage médical et ne doit pas recevoir de conversations réelles identifiables.

## Équipe

Ines Moalla · Nour Rajhi · Baha Saadaoui · Yosri Awedi · Safa Mahjoub · Samar Touil — Neuro Nova, Esprit.
