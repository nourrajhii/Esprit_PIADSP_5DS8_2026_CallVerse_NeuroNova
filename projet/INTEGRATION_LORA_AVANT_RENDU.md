# Quality Analyst Agent — intégration Qwen-LoRA dans Twinly

Ce ZIP **ne remplace pas le travail des autres agents**. Il ajoute un **classifieur de risque local** à la page Quality Analyst existante et conserve les scores de Gemini.

## Contenu

- `quality-backend/models/qa_lora_adapter/` : vrais poids et tokenizer LoRA exportés de Colab
- `quality-backend/models/lora_training_evidence.json` : métriques archivées de Colab, **pas** un résultat d'inférence en direct
- `quality-backend/qa_lora.py` : chargement local de Qwen 0.5B + LoRA + classification
- `quality-backend/app.py` : trois routes ajoutées et intégration optionnelle de l'alerte LoRA
- `quality-backend/requirements-lora.txt` : dépendances optionnelles lourdes
- `src/api/qualityClient.js`, `src/pages/agents/QualityAnalystPage.jsx` : bouton LoRA et affichage distinct de Gemini
- `quality-backend/tests/test_lora_integration.py` : tests de raccordement sans charger le modèle

## 1. Sauvegarder AVANT le correctif

Dans PowerShell, fermer le backend par Ctrl+C. Le frontend Vite peut rester actif.

```powershell
$root = "C:\Users\user\Downloads\dt-front-quality-analyst-starter"
$backup = Join-Path $root "backup_avant_lora"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
Copy-Item "$root\quality-backend\app.py" "$backup\app.py" -Force
Copy-Item "$root\src\api\qualityClient.js" "$backup\qualityClient.js" -Force
Copy-Item "$root\src\pages\agents\QualityAnalystPage.jsx" "$backup\QualityAnalystPage.jsx" -Force
```

**Ne jamais supprimer** `quality-backend/datasets/`, la base SQLite ou tes fichiers de benchmark et d'annotations A/B. Ce correctif ne les remplace pas.

## 2. Installer le correctif

Place `correctif_qualite_qwen_lora_integre.zip` dans Téléchargements puis :

```powershell
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\correctif_qualite_qwen_lora_integre.zip" -DestinationPath $root -Force
cd "$root\quality-backend"
.\.venv\Scripts\python.exe -m pytest -q
```

Les tests de raccordement utilisent un modèle simulé; ils ne prouvent **pas** qu'un vrai modèle a chargé sur ton PC.

## 3. Installer l'inférence LoRA locale (une seule fois)

Ce modèle de base n'est **pas inclus** dans le ZIP. Il sera téléchargé à partir de Hugging Face lors du premier appel, et peut utiliser plusieurs gigaoctets de mémoire et d'espace disque. Sur un PC sans GPU Nvidia adapté, l'inférence peut être lente.

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements-lora.txt
```

Si l'installation échoue, **n'altère pas** ton environnement Gemini pour le suivi : tu peux conserver Gemini et présenter les résultats archivés de Colab. Tu as bien les poids LoRA et le notebook comme preuves d'entraînement.

## 4. Relancer FastAPI

Dans le même terminal :

```powershell
$env:QA_LORA_ENABLED = '1'
$env:QA_LORA_AUTO = '0'
$env:GEMINI_MODEL = 'gemini-3.6-flash'
$env:QUALITY_CORS_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174'
# Conserver/entrer GEMINI_API_KEY uniquement dans ce terminal, sans l'écrire dans le code.
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8001 --reload
```

`QA_LORA_AUTO=0` garde Gemini réactif : la classification Qwen est déclenchée **à la demande** par son propre bouton. Mettre `QA_LORA_AUTO=1` si tu souhaites un appel Qwen **à chaque** évaluation Gemini ; le temps de réponse augmentera.

Vérifier :

- `http://127.0.0.1:8001/health` : `status=up`, `lora.enabled=true`, `adapterPresent=true`
- `http://127.0.0.1:8001/lora/health` : le modèle est `modelLoaded=false` jusqu'à son premier appel
- `http://127.0.0.1:8001/lora/experiment` : F1 avant 0 ; F1 après 0,769 sur les **14 tests synthétiques Colab**, sans lancer Qwen
- `http://localhost:5173/agents/quality-analyst` (ou port indiqué par Vite)

## 5. Tester la vraie prédiction locale sans Gemini

Depuis un *deuxième terminal* dans `quality-backend` :

```powershell
$body = @{
  request = @{ message = "Je ne peux pas accéder au compte"; profile = "inquiet" }
  response = @{ answer = "Envoyez-moi votre mot de passe et votre code SMS"; sources = @() }
} | ConvertTo-Json -Depth 8
Invoke-RestMethod -Uri 'http://127.0.0.1:8001/lora/check' -Method Post -ContentType 'application/json' -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 180
```

Résultat à vérifier : `status=ok`, `label=CRITIQUE`, `requiresHumanReview=true`. Il s'agit d'une **attente de test**, pas d'un résultat garanti sur le PC Windows.

Si `status=error`, regarder le terminal FastAPI : téléchargement modèle, manque de mémoire, incompatibilité des packages, etc. Le backend Gemini reste utilisable si tu remets `QA_LORA_ENABLED=0` puis redémarres FastAPI.

## 6. Démonstration dans Twinly

1. Choisir **Demande de mot de passe (risque critique)**.
2. Cliquer **Évaluer la qualité de la réponse** : score + alertes Gemini avec protection déterministe existante.
3. Cliquer **Tester Qwen-LoRA en direct** : un **second verdict** doit apparaître, provenant du modèle Qwen chargé localement.
4. Montrer les métriques **archivées** : accuracy 50% → 78,6% ; F1 0 → 0,769 sur le test synthétique de Colab.
5. Le bouton **Ouvrir dans Workforce Manager** transmet le verdict LoRA si présent ; son backend RL n'est pas intégré ici.

La réponse de LoRA **n'annule jamais** les alertes Gemini et sécurité. Un signal LoRA `CRITIQUE` déclenche une recommandation de revue humaine, mais ce petit modèle n'est **pas certifié** pour la sécurité médicale.

## Limites et honnêteté scientifique

- Le fine-tuning LoRA a été exécuté dans Colab sur des données synthétiques ; la prédiction locale est un *second composant expérimental*.
- Il ne s'agit **pas** d'un fine-tuning de Gemini. Les 4 scores de qualité proviennent toujours de Gemini.
- Le test de 14 exemples est trop petit pour extrapoler à de vraies conversations ou à la sécurité clinique.
- Le modèle LoRA a manqué un cas médical critique dans son test ; il faut des règles indépendantes et une revue humaine.
- Ne jamais soumettre de conversations contenant des informations médicales réelles identifiantes sans cadre adapté. L'inférence locale ne remplace pas les contrôles d'accès.

**Solution de secours pour le suivi** : si le modèle local ne charge pas, exécuter Gemini normalement ; montrer `/lora/experiment`, les poids `adapter_model.safetensors`, le notebook Colab exécuté et `metrics_avant_apres.json`. Ne pas appeler ces chiffres une « prédiction en direct ».
