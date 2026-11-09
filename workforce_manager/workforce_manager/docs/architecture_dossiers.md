# Architecture des dossiers – Workforce Manager Agent

## L'idée en une image

L'agent est le **chef du centre d'appels** de PharmaShop. Il travaille à deux niveaux :

```
NIVEAU MACRO : organiser l'équipe (toutes les 15 min)
  data/ (journées) ─▶ env/ (simulateur du centre) ◀──▶ policies/ (qui décide : règles, RL)
                                    │
                                    └─▶ evaluation/ (qui est le meilleur ? preuves, figures)

NIVEAU MICRO : traiter une conversation
  QualityEvaluation ─▶ micro/ (les règles DÉCIDENT) ─▶ llm/ (Gemini EXPLIQUE) ─▶ WorkforceDecision

ACCÈS EXTÉRIEUR
  api/ (FastAPI) expose les deux niveaux · demo.py les montre en direct · schemas.py = le contrat
```

**Règle d'or :** tout part de `schemas.py` (le contrat commun de l'équipe), et tout est vérifié par `tests/`.

---

## Les fichiers à la racine de `workforce_manager/`

| Fichier | Rôle |
|---|---|
| `schemas.py` | **Le contrat.** Modèles Pydantic copiés exactement sur `openapi.yaml` : `QualityEvaluation` (entrée), `WorkforceDecision` (sortie), `Kpi`. Tout champ hors contrat est refusé. |
| `demo.py` | **La démo en direct** de Sami, Inès et Karim : journée heure par heure, appel du persona, avant/après chiffré. |
| `README.md` | Présentation complète : architecture, commandes, résultats, limites. |
| `requirements.txt` | Les bibliothèques nécessaires (plages de versions). |
| `requirements-lock.txt` | Les versions **exactes** testées sur une machine neuve. |

---

## `data/` – les données simulées

Les autres agents ne sont pas branchés : on **simule** leurs sorties.

| Fichier | Rôle |
|---|---|
| `generate_mocks.py` | Génère 200 évaluations qualité réalistes (graine fixe = toujours les mêmes). |
| `mock_evaluations.json` | Ces 200 évaluations : bonnes réponses, information inventée, manque d'empathie, non-conformité santé, urgence mal gérée… |
| `scenarios.json` | Les 8 journées types : les situations de la grille d'évaluation (normale, pic d'activité, sous-effectif, incident technique, campagne commerciale, forte affluence) et les personas (Sami : rupture de stock ; Inès : urgence en heure de pointe ; Karim : tensiomètre défectueux). Pour chacune : appels par heure, prévision du planning, part santé/urgence, événements. |

## `env/` – le simulateur du centre (le « jeu vidéo »)

| Fichier | Rôle |
|---|---|
| `call_center_env.py` | **Le cœur.** Simule une journée de 8h à 20h, minute par minute : les appels arrivent, les conseillers répondent, les clients raccrochent s'ils attendent trop. Définit l'**état** (27 valeurs : files, conseillers, occupation, prévision, AHT, FCR, satisfaction, événements…) et les **10 actions** de la grille (affectation entre files, priorités, compétences, réserve, heures sup, planning…). Gère les rappels des clients non résolus et les absences. Environnement Gymnasium. |
| `reward.py` | Calcule la **récompense** (la « note ») de chaque quart d'heure : appels résolus, abandons, attente, coût… Le détail de chaque composante est conservé. |
| `random_scenarios.py` | Génère des **journées aléatoires** (de 150 à 1 500 appels) pour que l'agent sache gérer n'importe quelle journée. |
| `scenario_mix.py` | Pendant l'entraînement, tire au hasard une journée connue ou aléatoire. |
| `demo_sans_decision.py` | Montre le centre **sans aucun pilotage** : il s'effondre le jour de Sami (35 % d'abandons). |

## `config/` – les réglages métier

| Fichier | Rôle |
|---|---|
| `reward.yaml` | Les **poids de la récompense**, chacun justifié par une priorité PharmaShop. Exemple : un abandon coûte 2 points en standard, 5 en santé et 10 en urgence. On les modifie ici, sans toucher au code. |

## `policies/` – « qui décide » au niveau macro

| Fichier | Rôle |
|---|---|
| `no_action_policy.py` | Ne fait rien : le centre tel qu'il est aujourd'hui. |
| `random_policy.py` | Décide au hasard : le plancher. |
| `rule_policy.py` | **Le chef de plateau** : des règles si/alors simples. C'est la barre que l'IA doit battre. |
| `q_learning.py`, `train_q_learning.py` | IA simple (tableau de 108 cases) : entraînement et utilisation. |
| `analyse_q_table.py` | Affiche ce que le Q-learning a appris. |
| `ppo.py`, `train_ppo.py` | **IA principale (PPO, réseau de neurones)** : entraînement (variantes standard et généraliste) et utilisation. |
| `modeles/` | Les **modèles déjà entraînés** : `ppo_workforce_general.zip` (celui de l'API), `ppo_workforce.zip`, `q_table.npz`. |

## `responsable/` – l'agent responsable (garde-fous autour du PPO)

| Fichier | Rôle |
|---|---|
| `agent.py` | **AgentResponsable** : détection de l'inconnu (repli sur les règles), masquage des actions impossibles, validation des actions coûteuses, journal de chaque décision. |
| `domaine.py` | Apprend les bornes des situations vécues à l'entraînement (`domaine_connu.json`) et détecte une situation jamais vue. |
| `superviseur.py` | Validation des actions coûteuses : délégation par budget (défaut), chef de plateau en console (démo), réponse fixe (tests). |
| `explication.py` | Traduit l'état en langage clair et explique chaque action (utilisé par le journal et la démo). |

Réglages : `config/responsabilite.yaml`. Explications : `docs/agent_responsable.md`.

## `micro/` – décider pour une conversation

| Fichier | Rôle |
|---|---|
| `quality_rules.py` | Transforme une évaluation qualité en actions : réponse santé non conforme → `escalade_humain` (pharmacien) ; information inventée → `relancer_rag` + `signaler_kb`… Gère les doublons, les critères absents et les garde-fous santé. |
| `type_demande.py` | Déduit si la demande est standard, santé ou urgence à partir de la requête du client (entités, puis mots-clés de l'intention et du message). |

## `llm/` – expliquer en français (Gemini)

| Fichier | Rôle |
|---|---|
| `prompts/explain_v1.txt` | Le prompt système : rôle, règles absolues (ne rien décider, ne rien inventer), style, format JSON. |
| `prompts/exemples_v1.json` | 3 exemples d'apprentissage (Sami, Inès, Karim). |
| `explainer.py` | Appelle Gemini, lit le JSON, refait des essais si besoin, et **revient aux textes fixes** en cas d'échec. La clé est lue dans une variable d'environnement. |
| `verifications.py` | Les 6 contrôles automatiques de chaque texte : JSON valide, aucune action inventée, priorités inchangées, ton, longueur, aucun dosage médical. |

## `api/` – l'accès pour les autres (FastAPI)

| Fichier | Rôle |
|---|---|
| `main.py` | Les 3 endpoints : `POST /api/agents/workforce-manager` (le contrat), `POST …/simulate-day` (simuler une journée), `GET /api/kpi`. Plus le CORS pour le front et les erreurs au format de l'équipe. |
| `simulation.py` | Joue une journée pour l'API et convertit les résultats au format `Kpi` du Swagger. |
| `reponse.py` | Ajoute à la décision les champs affichés par le front : responsable de chaque action, statut, synthèse d'impact. |
| `exemples/` | Des requêtes prêtes à l'emploi (Sami, Inès, Karim), utilisées par la page `/docs` et par curl. |

## `evaluation/` – prouver que ça marche

| Fichier | Rôle |
|---|---|
| `run_policy.py` | Fait jouer une politique sur N journées et calcule les KPI (abandons, SLA, coût…). |
| `compare_policies.py` | Compare les 5 politiques sur les **mêmes** 50 journées, avec tests statistiques et figures. |
| `generalisation.py` | Teste l'agent sur **100 journées jamais vues**. |
| `validation.py` | Choisit le meilleur modèle pendant l'entraînement. |
| `eval_explainer.py` | Mesure la qualité des explications de Gemini sur 15 cas. |
| `figures/` | Les graphiques PNG pour le rapport et l'oral (courbes d'apprentissage, comparaisons, généralisation). |
| `resultats/` | Les chiffres bruts (CSV/JSON) derrière chaque figure et chaque tableau. Attention : `eval_explainer.*` contient un essai bloqué par le quota gratuit de Gemini, ce n'est pas encore la vraie mesure. |

## `tests/` – le filet de sécurité (267 tests)

Un fichier par partie : `test_mocks`, `test_env`, `test_reward`, `test_policies`, `test_rl`, `test_quality_rules`, `test_explainer`, `test_api`, `test_demo`, `test_stats`, `test_random_scenarios`.
Deux fichiers protègent **le contrat** :
- `test_contrat_openapi.py` compare `schemas.py` au `openapi.yaml` de l'équipe ;
- `test_contrat_requete.py` vérifie que les requêtes au format actuel du Swagger restent acceptées.

Aucun test n'appelle Internet : Gemini est remplacé par un faux client.

## `docs/` – documents

| Fichier | Rôle |
|---|---|
| `presentation_orale.md` | Le texte de 2 minutes, l'avant/après, les 8 questions du jury. |
| `integration_equipe.md` | **Comment brancher le front et les vrais agents** : architecture, ports, orchestrateur, tests. |
| `openapi_workforce_manager_v2.yaml` | Proposition de contrat v2 pour l'équipe : `request`, `kpi` et `type_demande` en entrée, champs du front en sortie. |
| `proposition_contrat_type_demande.md` | Ancienne proposition (`type_demande` seul), remplacée par la v2. |
| `openapi_simulate_day.yaml` | Le bloc YAML à ajouter au Swagger de l'équipe pour l'endpoint `simulate-day`. |
| `architecture_dossiers.md` | Ce document. |

---

## Le trajet d'une requête (exemple : Inès)

1. Le Quality Analyst envoie l'évaluation de la conversation d'Inès à `POST /api/agents/workforce-manager` (**api/main.py**).
2. **schemas.py** vérifie que la requête respecte le contrat ; sinon, l'API répond 422.
3. **micro/quality_rules.py** décide : la conformité santé est faible et l'urgence n'a pas été comprise, donc `escalade_humain` (haute) et `formation` (moyenne).
4. **llm/explainer.py** demande à Gemini de rédiger les explications ; **llm/verifications.py** les contrôle. En cas de problème, on garde les textes fixes.
5. L'API renvoie un `WorkforceDecision` conforme au Swagger.

## Où modifier quoi ?

| Je veux… | Fichier |
|---|---|
| changer les priorités métier de l'IA | `config/reward.yaml`, puis réentraîner PPO |
| changer un seuil de décision (ex. conformité < 70) | `micro/quality_rules.py` |
| améliorer les explications | `llm/prompts/explain_v1.txt` (créer une v2) |
| ajouter une journée type | `data/scenarios.json` |
| changer le nombre de conseillers ou les durées d'appel | `env/call_center_env.py` (constantes en haut du fichier) |
| ajouter un endpoint | `api/main.py` |

Après chaque modification : `python -m pytest workforce_manager/tests -q`.
