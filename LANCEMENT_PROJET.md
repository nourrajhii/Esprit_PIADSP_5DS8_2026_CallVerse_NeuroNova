# 🚀 Guide de lancement du projet Digital Twin PharmaShop

## Prérequis

- Python 3.10+
- Node.js 16+
- PostgreSQL 12+ (installé et démarré)
- Ollama (pour les modèles locaux)

---

## 📦 Installation initiale (une seule fois)

### 1. Créer la base de données PostgreSQL

```bash
# Ouvrir psql
psql -U postgres

# Créer la base de données
CREATE DATABASE callverse;

# Vérifier
\l
\q
```

### 2. Configuration des variables d'environnement

**Fichier : `RAG/.env`**
```env
# Base de données
DATABASE_URL=postgresql://postgres:VOTRE_MOT_DE_PASSE@localhost:5432/callverse

# Gemini (obligatoire pour Quality Analyst)
GEMINI_API_KEY=votre_clé_gemini_ici

# LLM Provider (gemini, groq ou ollama)
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-2.0-flash-exp

# Embeddings
EMBED_BACKEND=local
LOCAL_EMBED_MODEL=paraphrase-multilingual-MiniLM-L12-v2

# Ollama (si LLM_PROVIDER=ollama)
OLLAMA_HOST=http://localhost:11434
OLLAMA_LLM_MODEL=qwen2.5:7b

# Client Simulator
CLIENT_SIM_DIR=../client
```

**Fichier : `dt-front/.env`**
```env
VITE_API_URL=http://localhost:8000
VITE_USE_MOCK=false
```

**Fichier : `dashboard/.env`** (optionnel, il lit depuis RAG/.env)
```env
DATABASE_URL=postgresql://postgres:VOTRE_MOT_DE_PASSE@localhost:5432/callverse
```

### 3. Installation des dépendances

#### Backend Python (RAG)
```bash
cd C:\Users\samar\Desktop\PI\RAG
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

#### Client Simulator
```bash
cd C:\Users\samar\Desktop\PI\client
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

#### Dashboard Streamlit
```bash
cd C:\Users\samar\Desktop\PI\dashboard
pip install -r requirements.txt
```

#### Frontend React
```bash
cd C:\Users\samar\Desktop\PI\dt-front
npm install
```

---

## 🎯 Lancement du projet (ordre recommandé)

### Étape 1 : Démarrer PostgreSQL
```bash
# Windows (si installé comme service)
# PostgreSQL démarre automatiquement

# Vérifier que PostgreSQL écoute sur le port 5432
netstat -an | findstr 5432
```

### Étape 2 : Démarrer Ollama (si utilisé)
```bash
# Ouvrir un terminal dédié
ollama serve

# Dans un autre terminal, vérifier les modèles
ollama list

# Si besoin, télécharger le modèle
ollama pull qwen2.5:7b
```

### Étape 3 : Démarrer le Backend FastAPI (RAG)
```bash
# Terminal 1 - Backend principal
cd C:\Users\samar\Desktop\PI\RAG
venv\Scripts\activate
uvicorn backend.main:app --reload --port 8000

# Le backend sera accessible sur http://localhost:8000
# Swagger docs : http://localhost:8000/docs
```

**Vérifications :**
- Les tables PostgreSQL se créent automatiquement au démarrage
- Vérifier les logs pour confirmer la connexion DB
- Tester : `curl http://localhost:8000/api/health`

### Étape 4 : Démarrer le Frontend React
```bash
# Terminal 2 - Frontend principal
cd C:\Users\samar\Desktop\PI\dt-front
npm run dev

# Le frontend sera accessible sur http://localhost:5173
```

### Étape 5 : Démarrer le Dashboard Streamlit (optionnel)
```bash
# Terminal 3 - Dashboard BI
cd C:\Users\samar\Desktop\PI\dashboard
streamlit run app.py

# Le dashboard sera accessible sur http://localhost:8501
```

---

## 🧪 Tester le système

### 1. Via l'interface web (recommandé)
```
1. Ouvrir http://localhost:5173
2. Naviguer vers "Simulation" ou "Client Simulator"
3. Choisir un profil client (ex: "mécontent")
4. Choisir un thème (ex: "facturation")
5. Lancer la simulation
6. Voir les résultats des 4 agents
7. Aller dans "Dashboard" pour visualiser les KPIs
```

### 2. Via l'API directement (Swagger)
```
1. Ouvrir http://localhost:8000/docs
2. Tester POST /api/simulations avec ce JSON :
{
  "profile": "mecontent",
  "topic": "facturation",
  "urgency": "haute",
  "rag": true,
  "conversationMode": false,
  "messageCount": 1
}
```

### 3. Via le Dashboard Streamlit
```
1. Ouvrir http://localhost:8501
2. Explorer les 6 pages :
   - Vue globale
   - Tendances temporelles
   - Analyse par profil
   - Critères qualité
   - Alertes & Escalades
   - Conversations récentes
```

---

## 🔍 Vérifications et diagnostics

### Vérifier que tout fonctionne

#### Backend
```bash
# Tester l'API health
curl http://localhost:8000/api/health

# Tester les profils
curl http://localhost:8000/api/profiles

# Tester le Quality Analyst
curl http://localhost:8000/api/quality/health
```

#### Base de données
```bash
# Se connecter à PostgreSQL
psql -U postgres -d callverse

# Vérifier les tables
\dt

# Vérifier les vues
\dv

# Compter les conversations
SELECT COUNT(*) FROM sim_conversations;

# Quitter
\q
```

#### Frontend
```bash
# Ouvrir la console développeur (F12)
# Vérifier qu'il n'y a pas d'erreurs
# Vérifier que les requêtes API passent bien
```

---

## 🐛 Problèmes courants et solutions

### Problème 1 : "Module not found" (Python)
```bash
# Réinstaller les dépendances
pip install -r requirements.txt

# Vérifier l'environnement virtuel activé
# Windows : venv\Scripts\activate
```

### Problème 2 : PostgreSQL connection refused
```bash
# Vérifier que PostgreSQL tourne
# Windows : services.msc → PostgreSQL

# Vérifier les credentials dans .env
DATABASE_URL=postgresql://postgres:MOT_DE_PASSE@localhost:5432/callverse
```

### Problème 3 : GEMINI_API_KEY manquante
```bash
# Obtenir une clé gratuite sur https://aistudio.google.com/apikey
# Ajouter dans RAG/.env :
GEMINI_API_KEY=votre_clé_ici
```

### Problème 4 : Port déjà utilisé
```bash
# Trouver le processus qui utilise le port 8000
netstat -ano | findstr :8000

# Tuer le processus (remplacer PID)
taskkill /PID <PID> /F

# Ou utiliser un autre port
uvicorn backend.main:app --reload --port 8001
```

### Problème 5 : CORS errors (Frontend)
```bash
# Vérifier que VITE_API_URL pointe vers le bon backend
# dt-front/.env
VITE_API_URL=http://localhost:8000

# Redémarrer le frontend
npm run dev
```

### Problème 6 : Dashboard Streamlit ne se connecte pas à la DB
```bash
# Vérifier que DATABASE_URL est défini
# dashboard/.env ou copier depuis RAG/.env

# Tester la connexion
python -c "import psycopg2; psycopg2.connect('postgresql://postgres:pwd@localhost:5432/callverse')"
```

---

## 📊 Workflow typique d'utilisation

### Scénario 1 : Tester une conversation simple
```
1. Frontend (localhost:5173) → Page "Simulation"
2. Sélectionner : profile="mécontent", topic="facturation"
3. Cliquer "Lancer la simulation"
4. Observer les résultats des 4 agents
5. Aller dans Dashboard → voir les KPIs mis à jour
```

### Scénario 2 : Conversation multi-tours (1-5 échanges)
```
1. Frontend → Page "Simulation"
2. Activer "Mode conversation"
3. Choisir nombre de messages (1-5)
4. Lancer → voir le dialogue complet
5. Dashboard Streamlit → "Conversations récentes" → drill-down
```

### Scénario 3 : Simulation manuelle (Client Simulator)
```
1. Frontend → "Client Simulator" (page dédiée)
2. Générer un profil client
3. Page "Customer Advisor" → coller le message
4. Voir la réponse RAG
5. Page "Quality Analyst" → évaluer la réponse
6. Page "Workforce Manager" → voir les décisions
```

### Scénario 4 : Analyse BI (après plusieurs simulations)
```
1. Dashboard Streamlit (localhost:8501)
2. "Vue globale" → KPIs agrégés
3. "Tendances temporelles" → évolution dans le temps
4. "Analyse par profil" → comparer les 8 profils
5. "Alertes & Escalades" → voir les cas critiques
```

---

## 🛑 Arrêter proprement le projet

```bash
# Backend FastAPI : Ctrl+C dans le terminal
# Frontend React : Ctrl+C dans le terminal
# Dashboard Streamlit : Ctrl+C dans le terminal
# Ollama : Ctrl+C dans le terminal

# PostgreSQL continue de tourner en arrière-plan (OK)
```

---

## 📚 Ressources utiles

- **API Documentation** : http://localhost:8000/docs
- **Frontend** : http://localhost:5173
- **Dashboard BI** : http://localhost:8501
- **PostgreSQL Admin** : pgAdmin ou DBeaver
- **Logs Backend** : Terminal où tourne uvicorn
- **Logs Frontend** : Console navigateur (F12)

---

## 🎓 Commandes avancées

### Réinitialiser la base de données
```bash
psql -U postgres -d callverse

# Supprimer toutes les conversations
TRUNCATE sim_conversations, sim_turns, sim_sources, 
         quality_evaluations, workforce_decisions, sim_clients CASCADE;

# Ou recréer complètement
DROP DATABASE callverse;
CREATE DATABASE callverse;
\q
```

### Exporter les données pour analyse
```bash
# Export CSV depuis PostgreSQL
psql -U postgres -d callverse -c "\COPY (SELECT * FROM v_bi_full) TO 'C:\Users\samar\Desktop\export.csv' CSV HEADER"
```

### Tester en mode mock (sans backend)
```bash
# dt-front/.env
VITE_USE_MOCK=true

# Redémarrer le frontend
npm run dev
```

---

## ✅ Checklist de démarrage rapide

- [ ] PostgreSQL installé et démarré
- [ ] Base `callverse` créée
- [ ] Fichiers `.env` configurés (RAG, dt-front)
- [ ] Clé Gemini API obtenue et configurée
- [ ] Dépendances Python installées (RAG, client, dashboard)
- [ ] Dépendances Node installées (dt-front)
- [ ] Backend FastAPI lancé (port 8000)
- [ ] Frontend React lancé (port 5173)
- [ ] Dashboard Streamlit lancé (port 8501) - optionnel
- [ ] Première simulation testée avec succès
- [ ] Dashboard affiche les données

---

## 🎉 Félicitations !

Votre système Digital Twin est maintenant opérationnel ! 

Vous pouvez maintenant :
- Simuler des conversations client-conseiller
- Évaluer automatiquement la qualité
- Analyser les performances via les dashboards
- Identifier les points d'amélioration
- Optimiser le centre d'assistance

**Bon développement ! 🚀**
