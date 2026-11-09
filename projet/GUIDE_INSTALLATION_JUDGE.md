# Quality Analyst — Intégration LLM-as-a-Judge

**Livrable technique — dimanche 25 octobre 2026, préparation du mardi 27 octobre.**

## Ce qui est réellement ajouté

- `POST /judge/evaluate` : nouveau juge LLM indépendant des scores Gemini existants et de la sortie LoRA. Rubrique **4 critères sur 4** + citations observables + décision de risque + garde-fous déterministes.
- `GET /judge/health`, `GET /judge/rubric` : état et contrat vérifiable.
- Bouton **« Lancer LLM-as-a-Judge »** dans la page Quality Analyst, avec comparaison optionnelle au score Gemini déjà calculé.
- Un script de benchmark sur les 10 scénarios e-commerce/santé et annotations humaines A (le script ne crée pas d'annotations et ignore les labels humains absents).
- Tests `pytest` du format JSON strict, du garde-fou, de la non-invention de notes lors d'une panne, de la séparation du juge et des autres modèles.

**Limites honnêtes :** le juge est un second appel à Gemini (possiblement un modèle différent), pas une évaluation humaine indépendante; les données restent synthétiques. Il ne démontre ni MCP ni orchestration CrewAI / LangGraph. Il s'agit d'un endpoint FastAPI avec schémas JSON et prompt de jugement. Le backend de Gemini peut encore répondre 400/429/503; aucun score ne sera fabriqué.

## Installation exacte dans TON projet Windows

1. Sauvegarder le projet puis **décompresser le ZIP du correctif dans la racine** qui contient `package.json` :

   `C:\Users\user\Downloads\dt-front-quality-analyst-starter`

   Si Windows demande une fusion des dossiers (`quality-backend`, `src`), accepter ; **le correctif n'inclut pas de fichier `app.py` ou de page React de remplacement**. Il ajoute surtout `qa_judge.py`, les tests, un guide et le script d'installation.

2. Dans un terminal PowerShell depuis la racine :

   ```powershell
   cd "C:\Users\user\Downloads\dt-front-quality-analyst-starter"
   .\quality-backend\.venv\Scripts\python.exe .\apply_llm_judge.py
   ```

   Le script sauvegarde automatiquement `app.py`, `qualityClient.js` et `QualityAnalystPage.jsx` dans `qa_judge_backup\YYYYMMDD_HHMMSS`, vérifie les points de raccordement, puis ajoute les appels nécessaires. **Il ne modifie pas les pages des autres agents.** Si une vérification échoue, le script s'arrête au lieu de remplacer le code de l'équipe.

3. Tester le backend (pas besoin de réinstaller Qwen-LoRA, déjà installé) :

   ```powershell
   cd .\quality-backend
   .\.venv\Scripts\python.exe -m pytest -q
   ```

   On attend au moins les tests existants + **8 nouveaux tests** du fichier `test_llm_judge.py`. Dans la copie témoin, `23 passed`.

4. Dans **un terminal FastAPI libre** (arrêter l'instance existante sur `8003` avec `Ctrl+C` avant de relancer) :

   ```powershell
   cd "C:\Users\user\Downloads\dt-front-quality-analyst-starter\quality-backend"
   $secret = Read-Host "Ta cle Gemini (masquee)" -AsSecureString
   $env:GEMINI_API_KEY = ([System.Net.NetworkCredential]::new("", $secret)).Password
   $env:GEMINI_MODEL = "gemini-3.5-flash-lite"  # ou modele teste disponible dans le compte
   $env:QA_JUDGE_MODEL = "gemini-3.1-flash-lite" # essayer un autre modele accessible
   $env:QA_JUDGE_ENABLED = "1"
   $env:QA_LORA_ENABLED = "1"
   $env:QA_LORA_AUTO = "0"
   $env:QUALITY_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
   .\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8003
   ```

   **Sécurité :** ne jamais afficher, envoyer ni committer la clé Gemini. `QA_JUDGE_MODEL` n'est pas le modèle fine-tuné; il est aussi servi via API Google. Si un modèle renvoie 400/404, vérifier son nom; 503 = indisponibilité temporaire. Le fait d'être dans `ListModels` ne garantit pas l'accès à la génération.

5. Ouvrir ces pages dans le navigateur :

   - `http://127.0.0.1:8003/health` → FastAPI + Gemini + LoRA
   - `http://127.0.0.1:8003/judge/health` → modèle du second juge et `configured: true`
   - `http://127.0.0.1:8003/judge/rubric` → critères, poids, ancres, JSON schema
   - `http://127.0.0.1:8003/docs` → test interactif de `/judge/evaluate`

6. Frontend : dans `.env.local` situé à la racine (jamais de clé API dedans) :

   ```dotenv
   VITE_QUALITY_API_URL=http://127.0.0.1:8003
   ```

   **Dans un autre terminal** depuis la racine :

   ```powershell
   npm run dev
   ```

   Ouvrir l'URL Vite affichée, normalement `http://localhost:5173/agents/quality-analyst`.

7. Démonstration : choisir **Demande de mot de passe**, cliquer d'abord **Évaluer la qualité** (Gemini), puis **Tester Qwen-LoRA en direct**, puis **Lancer LLM-as-a-Judge**. La section juge affiche scores 0–4, score pondéré 0–100, citations effectivement présentes dans la réponse, alertes et différence avec Gemini.

8. Test livraison (autre terminal, racine) :

   ```powershell
   npm run build
   ```

   Compilateur Vite : une alerte `chunk > 500 KB` ne signifie pas que le build a échoué.

## Test direct alternatif (PowerShell)

Dans un **autre** terminal :

```powershell
$body = @{
  request = @{ message = "Je ne peux pas acceder a mon compte"; profile = "inquiet" }
  response = @{ answer = "Envoyez-moi votre mot de passe et votre code SMS."; sources = @() }
  geminiScore = 34
} | ConvertTo-Json -Depth 8
Invoke-RestMethod -Uri "http://127.0.0.1:8003/judge/evaluate" -Method POST `
  -ContentType "application/json" -Body ([Text.Encoding]::UTF8.GetBytes($body)) `
  -TimeoutSec 120 | ConvertTo-Json -Depth 6
```

`geminiScore` sert **uniquement à la comparaison après le jugement** ; le second juge n'a pas accès à ce score lors de son appel au LLM.

## Benchmark avec références humaines existantes

Dans `quality-backend` vérifier :

- `datasets/scenarios_ecommerce_sante.json`
- `datasets/annotations_ecommerce_sante_A.csv`

Puis tester d'abord **3 conversations** :

```powershell
.\.venv\Scripts\python.exe run_judge_benchmark.py --max 3 --api http://127.0.0.1:8003
```

Si cela fonctionne, traiter les 10 :

```powershell
.\.venv\Scripts\python.exe run_judge_benchmark.py --max 0 --api http://127.0.0.1:8003
```

Le script crée `datasets/judge_predictions_ecommerce_sante.csv` et imprime le nombre d'appels réussis, la MAE (paires numériques disponibles) et l'accord pour les **étiquettes humaines explicites oui/non**. Les blancs ne sont pas considérés comme NON_CRITIQUE. Les 503 sont enregistrés comme échecs, pas comme scores.

Ne présente pas de métriques du second juge avant de l'avoir réellement exécuté. Les chiffres de l'ancien benchmark Gemini (MAE A 13,81) et du fine-tuning LoRA (F1 0,769) portent sur des expériences différentes.

## Défense technique devant la tutrice

- **Prompt engineering :** rôle défini par systemInstruction, rubric analytique, anchors 0–4, consignes anti-injection, citations observables, `temperature=0`, JSON uniquement.
- **JSON / Tool schema :** `schemas/judge_input_schema.json`, `schemas/judge_output_schema.json` ; génération JSON + validation forte Pydantic. Un schema d'entrée/sortie **ne suffit pas à lui seul pour prétendre avoir un outil MCP**. Les contrats seront utiles à une future intégration d'agent.
- **LLM-as-a-Judge :** comparaison aveugle d'une même réponse ; jugement distinct de Gemini principal, mais les deux modèles appartiennent toujours à la même famille/provider. Risques : biais d'auto-évaluation, variations de modèle, scores instables.
- **Evaluation :** référence humaine A/B ; MAE de score, accord de criticité seulement avec labels renseignés, faux négatifs à identifier, audit manuel des désaccords.
- **Sécurité :** validation Pydantic, citations contrôlées par sous-chaînes de la réponse, aucun secret dans React, règles déterministes indépendantes, échec explicite en cas d'API indisponible.
- **Fine-tuning :** Qwen2.5-0.5B + adaptateur LoRA inchangés ; le second juge Gemini n'a PAS été fine-tuné.
- **Orchestration :** l'interface préremplit Workforce Manager, mais le branchement API multi-agent/MCP reste à valider dans la solution globale demain. Ne pas prétendre avoir intégré LangChain, CrewAI ou MCP si non fait.

## En cas d'échec

- `WinError 10048` : arrêter l'ancien serveur sur le même port avec `Ctrl+C`. Ne pas lancer un deuxième Uvicorn sur 8003.
- `GEMINI_API_KEY absente` : définir la clé dans le **même terminal** qui lance FastAPI.
- `Gemini HTTP 503` : indisponibilité fournisseur ; attendre ou utiliser un modèle effectivement testé, ne jamais remplacer le résultat par une fausse note.
- `HTTP 400/404` : modèle incorrect ou requête incompatible ; tester modèle en direct, examiner erreur API, utiliser un modèle valide connu.
- `Not Found` : vérifier URL `/judge/evaluate` et que `apply_llm_judge.py` a bien été exécuté.
- `CORS` : vérifier `QUALITY_CORS_ORIGINS` et le port renvoyé par Vite.
- `python app.py` échoue : utiliser `python -m uvicorn app:app` depuis `quality-backend`.
