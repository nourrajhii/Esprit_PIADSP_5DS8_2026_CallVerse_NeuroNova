# Agent responsable – les garde-fous autour du PPO

**Objectif :** un agent capable de traiter n'importe quelle journée, qui **sait quand il ne sait pas**, ne prend pas seul les décisions qui engagent de l'argent, et **explique chacune de ses décisions**.

Code : `responsable/` (agent, domaine connu, superviseur, explications). Réglages : `config/responsabilite.yaml`.

```
            état St
               │
     ┌─────────▼─────────┐  situation jamais vue ?   ┌──────────────────────────────┐
     │ 1. DOMAINE CONNU  │──────── oui ─────────────▶│ règles du chef de plateau    │
     └─────────┬─────────┘  (au moins 1 h de repli)  │ (politique de secours)       │
               │ non                                  └──────────────┬───────────────┘
     ┌─────────▼─────────┐                                           │
     │ PPO : probabilités│                                           │
     │ 2. MASQUAGE des   │  actions impossibles retirées              │
     │ actions impossibles│ avant le choix                            │
     └─────────┬─────────┘                                           │
               ├◀───────────────────────────────────────────────────┘
     ┌─────────▼─────────┐  action coûteuse ?        ┌──────────────────────────────┐
     │ 3. VALIDATION     │──────── oui ─────────────▶│ superviseur : accepte/refuse │
     │    HUMAINE        │                           │ refus -> organisation maintenue│
     └─────────┬─────────┘                           └──────────────────────────────┘
     ┌─────────▼─────────┐
     │ 4. JOURNAL        │  qui a décidé, quoi, pourquoi, confiance, validation
     └─────────┬─────────┘
               ▼ action At exécutée
```

## 1. Détection des situations inconnues

- **Apprentissage du domaine connu** : 19 200 états vécus par l'agent sur 400 journées tirées comme à l'entraînement (`python -m workforce_manager.responsable.domaine`). Pour chaque variable surveillée (files, attente, volume, prévision, abandons), on garde la valeur la plus haute rencontrée (quantile 99,9 %).
- **Détection** : une variable dépasse sa borne de plus de 10 % de l'étendue observée, ou **plusieurs événements surviennent en même temps** (jamais vu à l'entraînement).
- **Réaction** : l'agent passe la main aux **règles du chef de plateau** pendant au moins 1 heure, et écrit la raison dans le journal. Par exemple : « file_urgence = 1.00 (jamais plus de 0.20 à l'entraînement) ».

## 2. Masquage des actions impossibles

`CallCenterEnv.action_masks()` dit quelles actions sont possibles à l'instant présent. Il a été vérifié sur 14 400 cas : 0 écart avec ce que l'action fait réellement. Les actions impossibles sont retirées **avant** le choix, et l'agent prend la meilleure action réalisable.

**Résultat :** on passe de 15 à 20 actions impossibles par jour à **0**.

## 3. Validation humaine des actions coûteuses

La grille parle de **« proposer »** l'activation de conseillers supplémentaires et des heures supplémentaires. Ces décisions engagent de l'argent : ce sont des **propositions** soumises au superviseur.

| Action coûteuse | Coût engagé estimé |
|---|---|
| activer un conseiller supplémentaire | 2,0 points (au moins 1 h) |
| heures supplémentaires | 3,6 points (1 h majorée) |
| planifier un renfort | 4,0 points (2 h) |

Deux superviseurs sont disponibles :
- **Délégation** (par défaut, sans humain connecté) : une enveloppe de **80 points par jour**. Les heures sup sont refusées si elles ne sont pas justifiées (aucun client en attente, aucun événement, prévision normale).
- **Chef de plateau** (démo `--superviseur`) : l'humain répond **o/n** à chaque proposition, dans le terminal.

En cas de refus, l'organisation actuelle est maintenue et la raison est écrite dans le journal.

## 4. Journal d'explication

Une entrée par décision, renvoyée par l'API (`simulate-day` avec `policy: "responsable"`) et enregistrée par la démo (`evaluation/resultats/journaux/`) :

```json
{"heure": "10h00", "source": "agent PPO", "action_proposee": "heures_supplementaires",
 "action_executee": "heures_supplementaires", "confiance": 0.97, "peu_sur": false,
 "explication": "Un conseiller reste une heure de plus, coût majoré (4 appel(s) en attente, 1 conseiller(s) libre(s)).",
 "validation": {"accepte": true, "par": "délégation (budget)", "raison": "accepté par délégation (22/80 points engagés)"},
 "situation_inconnue": [], "actions_masquees": ["planifier_renfort"],
 "situation": {"files": {"standard": 3, "sante": 1, "urgence": 0}, "attente_min": 1.2, "occupation": 0.9,
               "prevision_appels_h": 64, "evenements": ["stock sante"]}}
```

La **confiance** est la probabilité que le réseau PPO donne à l'action choisie, parmi les actions possibles. En dessous de 50 %, la décision est signalée « peu sûre ».

## Résultats mesurés (`python -m workforce_manager.evaluation.evaluer_responsable`)

| Jeu de journées | Agent responsable face aux règles | Face au PPO brut |
|---|---|---|
| 8 journées types (50 chacune) | gagne **les 8** (41 à 50 journées sur 50, p ≤ 7·10⁻⁷) | même performance (aucun écart significatif) |
| 100 journées jamais vues | gagne **88 fois sur 100** (p = 7·10⁻¹²) | même performance |
| Cumul sous-effectif + rupture + incident | +70 (6/10) | **+101** (7/10) : le repli sur les règles aide |
| Volume ×3 imprévu | −73 (4/10, non significatif) | −62 : au-delà de la capacité du centre |
| Journée vide / 20 % d'urgences / 5 absents / prévision fausse | gagne **9 à 10 journées sur 10** | même performance ou mieux |

**Activité des garde-fous** (moyenne par journée) :

| Jeu de journées | Replis sur les règles | Propositions coûteuses (dont refusées) | Actions impossibles |
|---|---|---|---|
| Journées types | 0,2 | 24 (3) | **0** |
| Journées inconnues | 0,7 | 20 (2) | **0** |
| Cas extrêmes | 9 (27 sur 48 lors du cumul d'incidents) | 21 (3) | **0** |

**À retenir :** les garde-fous ne coûtent rien en performance. Ils suppriment les décisions absurdes, passent la main quand l'agent sort de son domaine, soumettent les dépenses à validation, et rendent chaque décision traçable.

## Limites honnêtes

- Le seuil de confiance (50 %) signale environ 18 décisions « peu sûres » par jour. Avec 10 actions, une probabilité de 35 à 50 % reste souvent un bon choix : ce seuil sert à orienter l'attention, pas à bloquer.
- La détection ne repère que les situations **plus chargées** que celles connues. Une journée très calme n'est pas signalée, mais l'agent la gère bien (10 journées gagnées sur 10).
- Le volume ×3 dépasse la capacité physique du centre : ni l'agent, ni les règles, ni le repli ne peuvent éviter environ 40 % d'abandons. Le journal le signale. C'est alors une décision humaine (renforts exceptionnels, message d'attente…).
- La validation humaine de l'API se fait par **délégation** (budget). La validation interactive o/n n'existe que dans la démo : une validation en temps réel dans le front demanderait un endpoint « propositions en attente ».
