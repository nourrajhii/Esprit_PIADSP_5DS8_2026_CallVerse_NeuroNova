# Correctif du LLM-as-a-Judge : JSON invalide HTTP 502

Ce correctif cible exclusivement `quality-backend/qa_judge.py`. Il ajoute un schéma
JSON au niveau de l'appel Gemini (`responseSchema`) et garde la validation Pydantic.
Les réponses illisibles ou invalides sont réessayées une fois; aucun score fictif
n'est produit. Le terminal affiche uniquement des types d'erreurs et chemins de
champs, sans données clients ni clés d'API.

## Installation Windows PowerShell

1. Télécharge `Correctif_Judge_JSON_502.zip` dans Downloads.
2. Arrête le serveur FastAPI 8003 avec **Ctrl+C** (pas Vite).
3. Lance dans PowerShell :

```powershell
$root = 'C:\Users\user\Downloads\dt-front-quality-analyst-starter'
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\Correctif_Judge_JSON_502.zip" -DestinationPath $root -Force
cd $root
.\quality-backend\.venv\Scripts\python.exe .\installer_correctif_judge_json.py
cd quality-backend
.\.venv\Scripts\python.exe -m pytest -q
```

4. Redémarre FastAPI dans **le terminal où ta clé Gemini est configurée** :

```powershell
$env:QA_JUDGE_ENABLED = '1'
$env:QA_JUDGE_MODEL = 'gemini-3.1-flash-lite'
$env:QA_LORA_ENABLED = '1'
$env:QA_LORA_AUTO = '0'
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8003
```

Si une clé Gemini n'est pas configurée dans ce terminal, entre-la sans affichage :

```powershell
$key = Read-Host 'Cle Gemini' -AsSecureString
$env:GEMINI_API_KEY = ([System.Net.NetworkCredential]::new('', $key)).Password
```

Ne jamais placer une clé Gemini dans un fichier du frontend ou la partager.

5. Clique sur **Lancer LLM-as-a-Judge** dans Twinly ou appelle
   `POST http://127.0.0.1:8003/judge/evaluate` comme avant.

## Si le 502 persiste

Lis les messages `LLM Judge:` dans le terminal FastAPI. Il distingue désormais :

- `schema de reponse invalide` : valeurs/champs inattendus;
- `JSON absent ou illisible` : sortie vide ou JSON malformé;
- `provider HTTP 400` : requête ou schéma non accepté par le modèle.

Partage la catégorie et les champs affichés, **jamais la clé API**.

### Validation

Le patch a passé 28 tests Python (dont 5 nouveaux) dans un environnement de
référence simulant l'API Gemini. **Aucun test réel de génération Gemini n'a été
réalisé ici** ; le fonctionnement réel doit être validé sur ta machine.
