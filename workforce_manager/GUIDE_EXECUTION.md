# Guide d'exécution – Workforce Manager Agent (CallVerse / PharmaShop)

Ce guide permet de faire tourner l'agent sur ta machine en 15 minutes environ, sans rien connaître du projet.
Les modèles sont **déjà entraînés** et inclus : tu n'as rien à réentraîner.

Pour comprendre le projet : `workforce_manager/README.md`. Pour la présentation : `workforce_manager/docs/presentation_orale.md`.

---

## 0. Ce qu'il te faut

| Élément | Détail |
|---|---|
| Python | **3.11 ou 3.12** (vérifier avec `python --version`) |
| Espace disque | environ 1,5 Go (PyTorch est lourd) |
| Connexion internet | pour l'installation seulement |
| Clé Gemini | **facultative** : sans clé, l'agent utilise des textes fixes et tout fonctionne |

Les commandes ci-dessous sont pour **Windows (PowerShell)**. Les équivalents pour Mac/Linux sont indiqués quand ils diffèrent.

---

## 1. Décompresser

Décompresse `callverse_workforce_manager.zip`, puis ouvre un terminal **dans le dossier `callverse_workforce_manager`**, celui qui contient ce guide et le dossier `workforce_manager/`.

> ⚠️ **Toutes les commandes se lancent depuis ce dossier**, jamais depuis l'intérieur de `workforce_manager/`.
> Sinon, Python affiche `ModuleNotFoundError: No module named 'workforce_manager'`.

---

## 2. Installer (une seule fois)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r workforce_manager/requirements.txt
```

- **Mac/Linux** : remplace la 2e ligne par `source .venv/bin/activate`.
- Une fois l'environnement activé, `(.venv)` apparaît au début de la ligne du terminal.
- L'installation dure **environ 5 minutes** (mesuré : 4 min 30 sur une machine neuve ; PyTorch représente l'essentiel).
- **Si Windows refuse `activate`** (« l'exécution de scripts est désactivée »), tape d'abord la commande suivante, puis relance `activate` :
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  ```

À chaque nouvelle session de terminal, il suffit de refaire `.venv\Scripts\activate`.

**Pour avoir exactement les mêmes versions que l'auteur** (mêmes chiffres au centième près), installe plutôt le fichier figé, testé sur une machine neuve :

```powershell
pip install -r workforce_manager/requirements-lock.txt
```

---

## 3. Vérifier que tout marche

```powershell
python -m pytest workforce_manager/tests -q
```

Résultat attendu : **262 passed, 5 skipped** (environ 2 minutes).
Les tests « skipped » sont normaux : ils comparent le code au fichier `openapi.yaml` de l'équipe (dossier `dt-front`), qui n'est pas dans l'archive. Si tu as ce fichier, indique son chemin et relance pytest. Le résultat devient alors **267 passed** :

```powershell
$env:OPENAPI_PATH = "C:\chemin\vers\dt-front\swagger\openapi.yaml"
```

---

## 4. Voir l'agent en action (démo)

```powershell
python -m workforce_manager.demo --persona sami --sans-llm
```

Ce que tu dois voir :
1. la journée de Sami (rupture de stock), **heure par heure**, de 8h à 20h ;
2. les décisions de l'**agent responsable** (réserve, priorités, routage par compétences, renforts planifiés, heures sup…) avec leur **confiance** et les **garde-fous** déclenchés (proposition refusée, repli sur les règles), plus le nombre de clients qui raccrochent, **comparé aux règles d'un chef de plateau** sur la même journée ;
3. à 10h30, l'appel de Sami : sa conversation est évaluée et les règles décident (relancer la recherche, signaler la base de connaissances, formation) ;
4. un tableau **avant / après** : avec l'agent, environ 10 % des clients raccrochent, contre environ 14 % avec les règles (plus la satisfaction, la résolution au premier contact et l'occupation).

Autres options :

| Option | Effet |
|---|---|
| `--persona ines` ou `--persona karim` ou `--persona tous` | changer de persona |
| `--detail` | chaque quart d'heure au lieu de chaque heure |
| `--pause 1` | une seconde entre chaque bloc (pratique pour présenter) |
| `--superviseur` | **tu valides toi-même** (o/n) chaque action coûteuse proposée par l'agent |
| sans `--sans-llm` | les explications sont rédigées par Gemini (clé nécessaire, voir étape 6) |

---

## 5. Lancer l'API

```powershell
python -m uvicorn workforce_manager.api.main:app --port 8000
```

Ouvre ensuite **http://localhost:8000/docs** dans le navigateur. Déplie un endpoint, clique sur **« Try it out »**, choisis l'exemple Inès, Sami ou Karim, puis clique sur **« Execute »**.

| Endpoint | Rôle |
|---|---|
| `POST /api/agents/workforce-manager` | une évaluation qualité → les décisions (contrat `openapi.yaml`) |
| `POST /api/agents/workforce-manager/simulate-day` | simuler une journée : `{"scenario": "sami_rupture_stock", "policy": "ppo"}` |
| `GET /api/kpi` | les KPI de la dernière simulation |

Test en ligne de commande, dans un **second** terminal, le premier faisant tourner l'API :

```powershell
curl.exe -X POST "http://localhost:8000/api/agents/workforce-manager?explications=false" -H "Content-Type: application/json" --data-binary "@workforce_manager/api/exemples/ines.json"
```

Réponse attendue : `escalade_humain` (priorité haute), puis `formation`.
Pour arrêter l'API : **Ctrl + C**.

Le front de l'équipe (`localhost:5173`) est autorisé à appeler l'API (CORS).

---

## 6. (Facultatif) Activer les explications Gemini

1. Crée **ta propre clé** sur https://aistudio.google.com/apikey (bouton « Create API key »). Ne réutilise jamais la clé de quelqu'un d'autre.
2. Enregistre-la pour ton compte Windows. Garde les guillemets, puis ferme et rouvre le terminal :
   ```powershell
   [Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "ta_cle_ici", "User")
   ```
   Sur **Mac/Linux**, ajoute `export GEMINI_API_KEY="ta_cle_ici"` dans `~/.zshrc` ou `~/.bashrc`.
3. Relance la démo **sans** `--sans-llm`. La ligne d'explication doit indiquer « rédigé par Gemini ».

> L'offre gratuite est limitée à **20 requêtes par jour et par modèle**. Une démo complète en consomme 3, et l'évaluation des 15 cas environ 15 à 20.
> Ne mets **jamais** la clé dans le code, dans un fichier ou sur GitHub.

---

## 7. (Facultatif) Tout recalculer

Inutile pour utiliser l'agent : les résultats et les modèles sont déjà dans l'archive.

| Pour… | Commande | Durée |
|---|---|---|
| Comparer les 5 politiques (tests statistiques + figures) | `python -m workforce_manager.evaluation.compare_policies` | ~15 min |
| Tester sur 100 journées inconnues | `python -m workforce_manager.evaluation.generalisation` | ~15 min |
| Réentraîner l'agent PPO utilisé par l'API | `python -m workforce_manager.policies.train_ppo --variante generaliste` | ~45 min |
| Mesurer la qualité des explications Gemini | `python -m workforce_manager.evaluation.eval_explainer` | ~3 min (clé requise) |

Les figures sont dans `workforce_manager/evaluation/figures/` et les chiffres dans `workforce_manager/evaluation/resultats/`.

---

## 8. Dépannage

| Problème | Solution |
|---|---|
| `ModuleNotFoundError: No module named 'workforce_manager'` | Tu n'es pas dans le bon dossier : place-toi dans celui qui **contient** `workforce_manager/` (étape 1). |
| `No module named 'torch'` (ou un autre module) | L'environnement n'est pas activé : refais `.venv\Scripts\activate`. |
| `activate` refusé par Windows | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, puis réessaie. |
| L'API ne démarre pas : port déjà utilisé | Utilise un autre port : `--port 8001`, puis ouvre http://localhost:8001/docs. |
| Accents illisibles dans le terminal | Tape `chcp 65001`, puis relance la commande. |
| Explications : « textes fixes (LLM indisponible) » | Normal sans clé. Avec une clé : 429 = quota du jour épuisé (réessaie demain) ; 503 = Google surchargé (réessaie plus tard) ; 404 = modèle retiré (choisis-en un autre avec `$env:GEMINI_MODEL = "gemini-3.5-flash"`). |
| `simulate-day` renvoie 503 « modele_non_entraine » | Le dossier `workforce_manager/policies/modeles/` manque : redécompresse l'archive. |
| Messages `oneDNN`, `absl` ou `StarletteDeprecationWarning` | Simples informations des bibliothèques, sans conséquence. |

---

## 9. Bonnes pratiques avant de modifier le projet

- **Le contrat commun** (`openapi.yaml`) appartient à toute l'équipe. Les extensions proposées par cet agent sont dans `workforce_manager/docs/` (`type_demande` optionnel et l'endpoint `simulate-day`) et attendent votre validation.
- **Après toute modification**, relance `python -m pytest workforce_manager/tests -q` : les tests vérifient notamment que la sortie respecte toujours le contrat.
- **Les graines aléatoires sont fixées** : les mêmes commandes donnent les mêmes chiffres sur toutes les machines (à l'arrondi près selon les processeurs pour l'entraînement PPO).
