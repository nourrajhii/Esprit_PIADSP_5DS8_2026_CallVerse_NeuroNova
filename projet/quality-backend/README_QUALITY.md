# Module Quality Analyst — vendredi 23 octobre

Ce dossier est **un nouveau module isolé**, pas une modification des autres agents. Le front global garde son mode mock, sauf le bouton « Évaluer » de la page Quality Analyst.

## Démarrage backend (PowerShell, depuis quality-backend)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Dans le même terminal définir la clé *sans l'écrire dans le code ni dans le ZIP* :

```powershell
$secret = Read-Host 'Clé Gemini' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try { $env:GEMINI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
$env:GEMINI_MODEL = 'gemini-2.5-flash'
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8001 --reload
```

- Health: http://127.0.0.1:8001/health
- Swagger API: http://127.0.0.1:8001/docs
- Post: `POST /evaluate` avec `{ "request": {"message":"...", "profile":"mecontent"}, "response": {"answer":"...", "sources":[]}}`
- `GET /kpis` / `GET /evaluations` retournent les résultats enregistrés dans SQLite.

**Important :** `mode=gemini-llm` n'apparaît qu'après un appel réel réussi. Sans clé, HTTP 503. Les tests offline valident le contrat et les calculs, pas les performances du modèle.

## Démarrage frontend (dans la racine où se trouve package.json)

```powershell
npm ci
npm run dev
```

Puis visite http://localhost:5173/agents/quality-analyst. Le front utilise l'API Quality à `http://127.0.0.1:8001` par défaut. Pour le changer, configurer `VITE_QUALITY_API_URL` dans un `.env.local` personnel (ne jamais le partager).

## Périmètre scientifique et limites

- Quatre scores **estimés par Gemini** : pertinence, empathie, clarté et conformité indicative. Le score global est une moyenne pondérée documentée.
- **Exactitude / groundedness** : `null` car des titres de sources ou le LLM seul ne prouvent pas la véracité des informations. Un module RAG de vérification sera nécessaire.
- Les messages dangereux déclenchent une alerte ciblée avec revue humaine. Ce détecteur n'est pas une conformité exhaustive.
- Le backend ne fait **pas de fine-tuning**. L'utilisation d'un LLM par API et le prompting ne sont pas du fine-tuning. Pour entraîner : labels humains, partitionnement par scénario, LoRA/QLoRA sur modèle open-weight, comparaison avant/après sur un test indépendant.
- Métriques à préparer : MAE/RMSE (notes vs annotations humaines), précision/rappel/F1 (risques), accord entre deux annotateurs, variance des scores pour trois répétitions.
- Ne jamais transmettre de données clients réelles identifiantes vers une API externe pour un prototype sans consentement et cadre de traitement appropriés.
- Le transfert vers Workforce Manager, dans le front partagé, navigue vers sa page : son algorithme réel n'est **pas** inclus dans ce module.

## Validation notée — jeu de test et métriques

- `datasets/scenarios_telecom.json` contient dix **cas fictifs à tester**, mais les scénarios ne sont pas une vérité terrain humaine.
- Après analyse, ouvre `GET /evaluations` et copie les vrais `conversationId` dans `datasets/annotations_template.csv`.
- Fais évaluer les conversations à l'aveugle par deux personnes indépendantes (deux fichiers CSV, sans voir la note Gemini). Si les notes divergent, documente un arbitrage.
- Depuis `quality-backend`, exécute : `python benchmark.py datasets/annotations_template.csv` après avoir rempli les scores humains.
- Pour prouver un fine-tuning, il faudra entraîner explicitement un modèle/LoRA avec des conversations annotées **distinctes** du test. Ni `benchmark.py` ni le prompting Gemini ne réalisent cet entraînement.
