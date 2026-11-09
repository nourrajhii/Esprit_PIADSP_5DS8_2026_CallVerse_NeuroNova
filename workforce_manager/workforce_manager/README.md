# Workforce Manager Agent – CallVerse (PharmaShop)

Agent n°4 du Digital Twin du centre de relation client **PharmaShop** (e-commerce + santé).
Il joue le rôle du **chef du centre**, à deux niveaux :

| Niveau | Question | Méthode | Entrée → sortie |
|---|---|---|---|
| **Macro** | Comment organiser l'équipe maintenant ? | Reinforcement Learning (PPO) | état du centre → action toutes les 15 min |
| **Micro** | Que faire après cette conversation ? | Règles métier + explication LLM | `QualityEvaluation` → `WorkforceDecision` |

Les autres agents (Client Simulator, Customer Advisor, Quality Analyst) ne sont pas intégrés :
leurs sorties sont **simulées** au format exact du contrat commun `openapi.yaml`.
Sami, Inès et Karim sont des **personas** (scénarios de test).

**Conformité à la grille d'évaluation des enseignants** (état, actions, récompense, scénarios) :
`docs/conformite_grille.md`.

**Agent responsable** : le PPO est entouré de 4 garde-fous. Il détecte les situations inconnues et se replie alors sur les règles, il ne choisit jamais une action impossible, il soumet les actions coûteuses à validation, et il tient un journal d'explication de chaque décision (`docs/agent_responsable.md`).

---

## Architecture

```
                        ┌──────────────────────── NIVEAU MACRO ────────────────────────┐
  data/scenarios.json   │  env/call_center_env.py         policies/                    │
  env/random_scenarios ─┼─▶ simulateur Gymnasium  ◀──────▶ PPO (généraliste) / règles │
  (8 journées types)    │  état (27 valeurs) → action (10) → récompense (9 composantes) │
                        └──────────────────────────────────────────────────────────────┘
                        ┌──────────────────────── NIVEAU MICRO ────────────────────────┐
  QualityEvaluation ───▶│  micro/quality_rules.py  ──▶  llm/explainer.py (Gemini)      │──▶ WorkforceDecision
  (Quality Analyst)     │  les RÈGLES décident          le LLM EXPLIQUE (jamais ne      │
                        │                               décide) + 6 vérifications       │
                        │                               + repli sur textes fixes        │
                        └──────────────────────────────────────────────────────────────┘
                                         api/main.py (FastAPI) expose les deux niveaux
```

```
workforce_manager/
├── schemas.py            Modèles Pydantic = copie exacte du contrat openapi.yaml (+ Kpi)
├── demo.py               Démo en direct des personas (macro + micro + avant/après)
├── responsable/          Agent responsable : domaine connu, superviseur, journal, explications
├── config/reward.yaml    Poids de la récompense, chacun justifié par le métier
├── data/                 200 évaluations simulées + 8 journées types (personas + grille)
├── env/                  Simulateur du centre, récompense, journées aléatoires
├── policies/             Rien, aléatoire, règles, Q-learning, PPO (+ modèles entraînés)
├── micro/                Décision par conversation (règles métier)
├── llm/                  Prompt v1, exemples few-shot, explainer Gemini, vérifications
├── api/                  API FastAPI + exemples de requêtes
├── evaluation/           Baselines, comparaison statistique, généralisation, figures
├── docs/                 Présentation orale, propositions de contrat pour l'équipe
└── tests/                Tests pytest (aucun appel réseau)
```

---

## Installation

Python 3.11 ou plus (testé avec 3.12), depuis le dossier qui **contient** `workforce_manager/` :

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r workforce_manager/requirements.txt
```

Versions exactes testées sur une machine neuve : `requirements-lock.txt`. Guide pas à pas pour un
coéquipier : `GUIDE_EXECUTION.md`, à la racine de l'archive envoyée.

**Clé Gemini (optionnelle).** Sans clé, l'agent fonctionne avec les textes fixes. Pour l'obtenir :
https://aistudio.google.com/apikey. Ne jamais la mettre dans le code :

```bash
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "ta_cle_ici", "User")
```

Modèle utilisé : `gemini-3.6-flash` (modifiable avec la variable `GEMINI_MODEL`). Offre gratuite :
20 requêtes par jour et par modèle.

---

## Démarrage rapide

```bash
python -m pytest workforce_manager/tests -q
python -m workforce_manager.demo --persona sami --pause 1
python -m uvicorn workforce_manager.api.main:app --port 8000 --reload
```

Options de la démo : `--persona sami|ines|karim|tous`, `--detail` (chaque quart d'heure),
`--superviseur` (vous validez vous-même chaque action coûteuse, o/n),
`--sans-llm` (n'utilise pas le quota Gemini), `--journees N` (taille de l'avant/après).

---

## Toutes les commandes, par étape

| Étape | Commande | Durée CPU |
|---|---|---|
| Données simulées | `python -m workforce_manager.data.generate_mocks` | < 1 s |
| Journée sans décision | `python -m workforce_manager.env.demo_sans_decision` | < 1 s |
| Baselines | `python -m workforce_manager.evaluation.run_policy` | ~3 min |
| Q-learning | `python -m workforce_manager.policies.train_q_learning` | ~15 min |
| Ce que le Q-learning a appris | `python -m workforce_manager.policies.analyse_q_table` | ~10 s |
| PPO standard | `python -m workforce_manager.policies.train_ppo` | ~25 min |
| PPO généraliste (défaut de l'API) | `python -m workforce_manager.policies.train_ppo --variante generaliste` | ~45 min |
| Comparaison statistique | `python -m workforce_manager.evaluation.compare_policies` | ~15 min |
| Généralisation (100 journées) | `python -m workforce_manager.evaluation.generalisation` | ~15 min |
| Règles micro (200 mocks) | `python -m workforce_manager.micro.quality_rules` | < 1 s |
| Explications LLM (15 cas) | `python -m workforce_manager.evaluation.eval_explainer` | ~3 min, clé requise |
| Domaine connu (après entraînement) | `python -m workforce_manager.responsable.domaine` | ~3 min |
| Effet de l'agent responsable | `python -m workforce_manager.evaluation.evaluer_responsable` | ~15 min |

---

## API (FastAPI)

Documentation interactive : http://localhost:8000/docs (exemples Sami, Inès, Karim préremplis).

| Endpoint | Rôle |
|---|---|
| `POST /api/agents/workforce-manager` | contrat `openapi.yaml` : `evaluation` (+ `type_demande` optionnel) → `WorkforceDecision` |
| `POST /api/agents/workforce-manager/simulate-day` | `{scenario, policy, seed}` → 48 décisions + KPI au format `Kpi` |
| `GET /api/kpi` | KPI de la dernière simulation (404 si aucune) |

- Politiques : `none`, `random`, `rules`, `qlearning`, `ppo` (généraliste brut), `ppo_standard`, `responsable`
  (**recommandé** : PPO + garde-fous, avec renvoi du `journal` de chaque décision).
- Requête : `evaluation`, plus `request`, `kpi` et `type_demande` (tous facultatifs, déjà envoyés par le front).
  Si `type_demande` est absent, il est déduit de `request`.
- Réponse : le contrat (`problems`, `actions`), plus les champs lus par le front (`responsible`, `status`,
  `auditScore`, `workforceSummary`…). `?strict=true` renvoie le contrat v1 seul.
- En-têtes `X-Explication-Source` (`llm`, `fallback`, `sans_objet`, `desactive`) et `X-Type-Demande-Source`.
- `?explications=false`, ou la variable `WM_LLM=off` : réponse immédiate, sans appel au LLM.
- Intégration avec le front et les autres agents : `docs/integration_equipe.md`.
- Erreurs au format `Error {code, message}` du Swagger ; CORS ouvert au front `localhost:5173`.

Exemple :

```bash
curl.exe -X POST "http://localhost:8000/api/agents/workforce-manager" -H "Content-Type: application/json" --data-binary "@workforce_manager/api/exemples/ines.json"
```

Propositions pour l'équipe (le `openapi.yaml` partagé n'est pas modifié) :
`docs/proposition_contrat_type_demande.md` et `docs/openapi_simulate_day.yaml`.

---

## Résultats (version 2, conforme à la grille)

**Agent PPO (modèle par défaut) face au chef de plateau** : 50 journées identiques par scénario, soit les 8 situations de la grille et des personas.

| Journée | Abandons | Urgences < 3 min | Satisfaction /5 | Occupation | Récompense | Journées gagnées |
|---|---|---|---|---|---|---|
| Normale | 6,0 % → **1,2 %** | 89 % → **99,8 %** | 3,73 → **3,96** | 77 % → 64 % | 317 → **460** | 50/50 |
| Pic d'activité (Inès) | 8,5 % → **2,9 %** | 95 % → **99,9 %** | 3,58 → **3,82** | 82 % → 71 % | 256 → **484** | 49/50 |
| Sous-effectif | 7,5 % → **2,9 %** | 86 % → **99,5 %** | 3,66 → **3,84** | 81 % → 72 % | 245 → **393** | 50/50 |
| Incident technique | 10,5 % → **3,8 %** | 91 % → **99,9 %** | 3,57 → **3,85** | 79 % → 69 % | 247 → **464** | 49/50 |
| Campagne commerciale | 7,4 % → **2,2 %** | 91 % → **99,9 %** | 3,68 → **3,92** | 81 % → 72 % | 409 → **605** | 50/50 |
| Forte affluence | 10,8 % → **7,9 %** | 94 % → **99,9 %** | 3,47 → **3,58** | 90 % → 86 % | 203 → **343** | 41/50 |
| Sami (rupture de stock) | 14,2 % → **9,6 %** | 98 % → **99,9 %** | 3,34 → **3,51** | 86 % → 80 % | −52 → **116** | 45/50 |
| Karim (dispositif médical) | 9,3 % → **3,6 %** | 94 % → **99,9 %** | 3,54 → **3,79** | 82 % → 73 % | 181 → **402** | 48/50 |

- Sans aucun pilotage, 35 % des clients raccrochent le jour de Sami, et 38 % en forte affluence.
- L'agent ramène l'**occupation dans la plage raisonnable** (60-85 %), alors que les règles poussent l'équipe jusqu'à 90 %.
- La contrepartie : l'agent coûte de 44 à 64 points de plus en personnel.
- La **résolution au premier contact** (environ 75 %) dépend surtout de la qualité des réponses. Elle bouge peu avec le pilotage : c'est le rôle du niveau micro.

**Preuves statistiques** (Wilcoxon apparié, IC 95 % par bootstrap, correction de Holm) :
- **Sur les 8 journées**, l'agent bat les règles de 41 à 50 journées sur 50 (p ≤ 4·10⁻⁹ partout).
- **Sur 100 journées jamais vues** (150 à 1 500 appels, 7 types d'événements), il bat les règles **92 fois sur 100** (p = 5·10⁻¹⁴).
- Le **Q-learning tabulaire** ne voit que 4 variables sur 27. Il fait jeu égal avec les règles sur les journées calmes, mais il est nettement moins bon dans les crises (Sami : −103, forte affluence : −274). C'est un argument pour PPO.

**Niveau micro :** 100 % des cas graves des mocks sont traités (non-conformité santé → escalade 24/24, urgence mal gérée 14/14, information inventée 30/30, base incomplète 16/16).

**LLM :** le taux de réussite des explications reste à mesurer (`eval_explainer`). L'évaluation du 21/10 a été bloquée par le quota gratuit de Gemini, et non par la qualité du prompt.

Figures, dans `evaluation/figures/` :

| Fichier | Contenu |
|---|---|
| `comparaison_sami_abandons.png` | Abandons cumulés pendant la rupture de stock |
| `comparaison_recompenses.png`, `comparaison_differences.png` | Les 5 politiques sur les 8 journées, et leurs écarts |
| `generalisation_volume.png` | Résultats sur les 100 journées inconnues |
| `q_learning_courbe.png`, `ppo_courbe.png`, `ppo_general_courbe.png` | Courbes d'apprentissage |

---

## Choix de conception (résumé)

- **Conformité à la grille** : un état de 27 variables, 10 actions, une récompense en 9 composantes et les 6 scénarios demandés (détail dans `docs/conformite_grille.md`).
- **Le LLM n'a aucun pouvoir de décision.** Le type et la priorité des actions viennent des règles. Les textes de Gemini passent 6 vérifications, sinon l'agent revient aux textes fixes.
- **Récompense métier** (`config/reward.yaml`). L'unité est un appel standard résolu au premier contact. Un abandon coûte toujours plus qu'un appel ne rapporte (2, 5 ou 10 points selon standard, santé ou urgence). L'occupation est pénalisée hors de la plage 60-85 %.
- **PPO généraliste.** Il est entraîné à 50 % sur des journées aléatoires, pour fonctionner sur n'importe quelle journée, pas seulement sur les personas.
- **Reproductibilité.** Les graines sont fixées partout : entraînement 100 000+ (journées aléatoires 10 000 000+), validation 50 000+, évaluation 0-49, test de généralisation 900 000+. L'agent n'est jamais évalué sur une journée qu'il a vue.

## Limites connues

- Le PPO brut tente des actions impossibles (environ 15 par jour). L'agent responsable les masque (0 par jour).
- Au-delà de la capacité physique du centre (volume ×3), aucune politique n'évite environ 40 % d'abandons. L'agent le détecte, se replie sur les règles et le trace : la décision redevient humaine.
- La satisfaction (de 1 à 5) et la résolution au premier contact sont **simulées** à partir de la qualité des réponses et de l'attente. Elles ne sont pas mesurées auprès de vrais clients.
- Les données sont simulées. Les comparaisons entre politiques sont valables, mais les chiffres absolus dépendent du calibrage.

Présentation orale, avant/après détaillé et questions du jury : `docs/presentation_orale.md`.
