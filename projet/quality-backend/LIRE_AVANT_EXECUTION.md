# Étape 5 — Benchmark du Quality Analyst Agent

**Ce pack ne remplace aucun fichier du backend.** Il ajoute seulement le script `run_10_evaluations.ps1` à la racine de `quality-backend`.

## Conditions

- FastAPI est démarré sur http://127.0.0.1:8001 avec GEMINI_API_KEY défini et GEMINI_MODEL configuré.
- Le dossier `quality-backend/datasets/` comporte déjà `scenarios_telecom.json` et `annotations_template.csv`.
- L'appel à Gemini peut consommer un quota payant et occasionner des erreurs 429 ou 503.
- Chaque identifiant de scénario est stable (`01-bonne-prise-en-charge`, etc.). Une nouvelle évaluation du même identifiant remplace son rapport dans la base : ne pas confondre le nombre de lignes avec le nombre total d'appels.

## Mise en place

1. Décompresser ce ZIP dans un dossier temporaire.
2. Copier **uniquement** `run_10_evaluations.ps1` dans le dossier `quality-backend` de votre projet.
3. Garder FastAPI ouvert dans son terminal actuel.
4. Dans **un second terminal PowerShell**, depuis `quality-backend`, exécuter :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run_10_evaluations.ps1
```

La commande ne modifie pas la politique d'exécution de manière permanente. Le script envoie les dix conversations à l'API puis produit `datasets/benchmark_predictions.csv`.

## Annotation humaine

Copier `datasets/annotations_template.csv` sous `datasets/annotations_A.csv`, puis compléter les colonnes :

- `conversation_id`: identifiant exact du scénario.
- `pertinence_humaine`, `empathie_humaine`, `clarte_humaine`, `conformite_humaine`: notes 0–100, selon une grille écrite.
- `critique_humain`: `oui` ou `non` (une réponse exige-t-elle une escalade pour violation de sécurité ?).
- `annotateur`: code de l'évaluateur (A, B), `commentaire`: justification textuelle.

**Très important :** renseigner les notes **sans lire les prédictions Gemini** (annotation à l'aveugle). Un deuxième annotateur remplit indépendamment `annotations_B.csv`. Définir la grille, comparer A/B et arbitrer les désaccords avant de mesurer la qualité de Gemini.

Une fois A terminé, depuis `quality-backend`, exécuter :

```powershell
.\.venv\Scripts\python.exe benchmark.py datasets/annotations_A.csv
```

Ce script existant calcule MAE, RMSE et P/R/F1 pour le signal critique, en appariant les identifiants avec les rapports SQLite. Avec seulement 10 scénarios, il s'agit d'une **évaluation exploratoire**, non d'une précision générale. Ne pas utiliser ces dix scénarios à la fois pour entraîner et tester un modèle.

## Cas particuliers à discuter

- Scénario 03 (phishing bien traité) : distinguer le risque subi par le client de la faute du conseiller.
- Scénario 04 (demande de mot de passe) : conformité et escalade humaine critiques.
- Scénario 08 (allégation sur les 20 Go) : sans fiches produit officielles, l'exactitude demeure **non vérifiable**, et non automatiquement fausse.
- Les modèles peuvent être indisponibles momentanément. Le script note alors `ERREUR` au lieu d'inventer un score.

## Fine-tuning — étape suivante

Le benchmark ci-dessus n'entraîne aucun modèle. Pour répondre à la demande de fine-tuning, il faudra créer un jeu annoté plus large, choisir un modèle **dont les poids ou adaptateurs sont entraînables**, isoler des jeux train/validation/test sans fuite, effectuer réellement le fine-tuning (par exemple LoRA/QLoRA), puis comparer le modèle de base et le modèle ajusté sur les mêmes données de test. Gemini par appel API ne devient pas fine-tuné par simple modification du prompt.
