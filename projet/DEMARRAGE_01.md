# Étape 1 — Démarrer uniquement le Quality Analyst réel

**Pour le suivi de vendredi 23 octobre :** ta partie existe déjà dans React. Ce pack branche seulement le bouton d’évaluation au nouveau backend FastAPI avec Gemini (port 8001). Les autres agents restent en simulation.

## 1. Préparation

Décompresse le ZIP. Dans VS Code, ouvre le dossier contenant `package.json`, `src/` et `quality-backend/`.

## 2. Terminal A : démarrer ton backend (PowerShell)

```powershell
Set-Location -LiteralPath '.\quality-backend'
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

**Résultat attendu : 7 tests verts.** Ce sont des tests de schéma/score/API avec un fournisseur LLM simulé pendant les tests : ils ne prouvent pas que Gemini a déjà répondu en direct.

Ajoute la clé Gemini **sans l’écrire dans le code** :

```powershell
$secret = Read-Host 'Clé Gemini' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try { $env:GEMINI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
$env:GEMINI_MODEL = 'gemini-2.5-flash'
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8001 --reload
```

Ouvre `http://127.0.0.1:8001/health` et confirme `"status":"up"`, `"llmConfigured":true`. L'état de santé ne démontre pas encore qu'un appel LLM a réussi.

## 3. Terminal B : frontend React

Ouvre un **nouveau terminal PowerShell** à la racine (où `package.json` se trouve), puis :

```powershell
npm ci
npm run dev
```

Visite **http://localhost:5173/agents/quality-analyst**. Sélectionne un scénario et clique « Évaluer la qualité ». Un vrai rapport Gemini contient `mode: gemini-llm` avec scores, justifications, recommandations et signalement des risques. Sans clé/quota, l’interface affiche une erreur (pas de fausse note).

## 4. Vérifier et démontrer

- Teste les trois scénarios du frontend et compare leurs résultats.
- Dans `http://127.0.0.1:8001/docs`, lance `GET /evaluations` pour revoir les rapports et `GET /kpis` pour les KPI calculés.
- Dans `quality-backend/datasets/scenarios_telecom.json`, tu as 10 scénarios additionnels ; ils ne sont **pas** annotés humainement.
- Dans `quality-backend/datasets/annotations_template.csv`, prépare de vraies annotations humaines, puis `python benchmark.py datasets/annotations_template.csv` pour calculer MAE/RMSE/F1 quand elles seront disponibles.
- **Important :** les critères « exactitude » et « groundedness » sont affichés **Non vérifié**, pas des scores inventés, sans référence documentaire fiable.

## 5. Prochaines étapes après capture d'écran

1. Vérifier une réponse Gemini de bout en bout.
2. Valider le contrat et les transferts avec le Workforce Manager de ton groupe (la navigation existe, son algorithme n’est pas encore raccordé ici).
3. Évaluer la fiabilité contre des annotations humaines ; documenter les limites.
4. Monter une vraie expérience de fine-tuning (LoRA/QLoRA sur modèle open-weight) **si GPU et données étiquetées suffisantes**, puis comparaison avant/après sur un jeu de test séparé. Le pack fourni **ne contient pas** un modèle fine-tuné.

## Isolation des modifications

- **Modifié** : `src/pages/agents/QualityAnalystPage.jsx` (appel API dédié + affichage des non-vérifiés, alertes et preuves)
- **Ajouté** : `src/api/qualityClient.js`, `quality-backend/`, ce guide
- **Non modifiés** : les pages Client Simulator, Customer Advisor, Workforce Manager, le simulateur global et le swagger partagé
- Les fichiers `.env` ont été exclus du ZIP par précaution ; crée tes variables localement dans le terminal.
