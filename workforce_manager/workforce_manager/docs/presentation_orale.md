# Présentation orale – Workforce Manager Agent

## 1. Texte de 2 minutes (≈ 300 mots, à dire calmement)

> Mon agent, c'est le **Workforce Manager** de CallVerse : le chef du centre de relation client de PharmaShop. Son objectif est de piloter les ressources humaines du centre pour maintenir un bon niveau de service tout en maîtrisant les coûts.
>
> C'est un **agent de Reinforcement Learning**, et le **Digital Twin** du centre est son environnement d'apprentissage. Toutes les quinze minutes, il observe l'**état** du centre : 27 indicateurs, dont les files d'attente, les conseillers libres et occupés, le taux d'occupation, le volume entrant, la prévision de charge, les abandons, la durée de traitement, la résolution au premier contact, la satisfaction et les événements en cours. Il choisit une **action** parmi dix : affecter ou réaffecter des conseillers entre les files, appeler la réserve, modifier les priorités, router selon les compétences, lancer des heures sup, planifier un renfort ou ne rien changer. La simulation calcule ensuite une **récompense**, qui combine résolution, attente, abandons, SLA, occupation raisonnable, satisfaction et coûts. Après des milliers de journées, l'agent apprend une politique qui maximise cette récompense.
>
> Je l'ai entraîné sur les six situations demandées : journée normale, pic d'activité, sous-effectif, incident technique, campagne commerciale et forte affluence. J'y ai ajouté des journées générées au hasard, pour qu'il soit robuste.
>
> **Le résultat :** face aux règles d'un chef de plateau, mon agent gagne sur **les huit journées types**, sur 41 à 50 journées sur 50, avec des tests statistiques significatifs. En sous-effectif, par exemple, les abandons passent de 7,5 % à **2,9 %**, et l'occupation revient dans une plage raisonnable. Sur **100 journées jamais vues**, il bat le chef de plateau **92 fois sur 100**.
>
> Enfin, pour chaque conversation, des règles métier décident des actions correctives. Un LLM, Gemini, les **explique** en français, mais **ne décide jamais**. Et l'agent est **responsable** : il repère les situations qu'il n'a jamais vues et laisse alors la main aux règles, il ne propose jamais d'action impossible, il soumet les dépenses à validation, et il explique chacune de ses décisions dans un journal. Tout est accessible par une API conforme au contrat de l'équipe, et vérifié par plus de 260 tests automatiques.

**Ce qu'on montre pendant ce temps :**
- `evaluation/figures/ppo_courbe.png` (la courbe qui monte) ;
- `evaluation/figures/comparaison_recompenses.png` (les 8 journées) ;
- puis la démo en direct : `python -m workforce_manager.demo --persona ines --pause 1`, ou bien `--superviseur` pour valider soi-même, devant le jury, les actions coûteuses proposées par l'agent.

---

## 2. Avant / après (règles du chef de plateau → agent PPO, 50 journées identiques)

| Journée de la grille | Abandons | Urgences < 3 min | Satisfaction /5 | Occupation | Récompense |
|---|---|---|---|---|---|
| Situation normale | 6,0 % → **1,2 %** | 89 % → **99,8 %** | 3,73 → **3,96** | 77 % → 64 % | 317 → **460** |
| Pic d'activité (Inès) | 8,5 % → **2,9 %** | 95 % → **99,9 %** | 3,58 → **3,82** | 82 % → 71 % | 256 → **484** |
| Sous-effectif | 7,5 % → **2,9 %** | 86 % → **99,5 %** | 3,66 → **3,84** | 81 % → 72 % | 245 → **393** |
| Incident technique | 10,5 % → **3,8 %** | 91 % → **99,9 %** | 3,57 → **3,85** | 79 % → 69 % | 247 → **464** |
| Campagne commerciale | 7,4 % → **2,2 %** | 91 % → **99,9 %** | 3,68 → **3,92** | 81 % → 72 % | 409 → **605** |
| Forte affluence | 10,8 % → **7,9 %** | 94 % → **99,9 %** | 3,47 → **3,58** | 90 % → 86 % | 203 → **343** |
| Sami (rupture de stock) | 14,2 % → **9,6 %** | 98 % → **99,9 %** | 3,34 → **3,51** | 86 % → 80 % | −52 → **116** |
| Karim (dispositif médical) | 9,3 % → **3,6 %** | 94 % → **99,9 %** | 3,54 → **3,79** | 82 % → 73 % | 181 → **402** |

**La contrepartie à assumer :** l'agent mobilise plus de personnel, de 44 à 64 points de coût en plus. La récompense nette reste largement positive, de +140 à +228 par journée.

Repère sans pilotage : 35 % des clients raccrochent le jour de Sami, et 38 % en forte affluence.

---

## 3. Les 9 questions probables du jury

**1. « Montrez-moi la boucle d'apprentissage. »**
> `env/call_center_env.py` : `reset()` démarre une journée et renvoie l'état S0. `step(action)` applique At, simule 15 minutes minute par minute, puis renvoie la récompense Rt et le nouvel état St+1. Une journée correspond à 48 pas. La politique π(a|s) est un réseau de neurones PPO entraîné sur 12 500 journées ; sa courbe d'apprentissage passe de 3 à 338.

**2. « Pourquoi du Reinforcement Learning, alors que des règles simples marchent déjà ? »**
> Les règles réagissent quand la file déborde déjà. L'agent a appris à **anticiper** grâce à la prévision de charge : il planifie des renforts avant la montée, au coût normal plutôt qu'en heures sup. Il bat les règles sur les 8 journées, et c'est significatif partout (Wilcoxon apparié, p ≤ 4·10⁻⁹ après correction de Holm). Les règles restent utiles : elles servent de barre à battre.

**3. « Comment savez-vous que l'agent n'a pas appris ses scénarios par cœur ? »**
> Les journées d'entraînement, de validation et d'évaluation ont des graines différentes. Surtout, j'ai testé l'agent sur **100 journées inventées au hasard**, de 150 à 1 500 appels, avec 7 types d'événements. Il bat le chef de plateau **92 fois sur 100**.

**4. « Comment avez-vous choisi la récompense ? »**
> Chaque poids est justifié par une priorité de PharmaShop et réglable dans `config/reward.yaml`. L'unité est un appel standard résolu au premier contact. Un abandon coûte toujours plus qu'un appel ne rapporte : 2 points en standard, 5 en santé, 10 en urgence. L'occupation est pénalisée hors de 60-85 %, car au-delà viennent la fatigue et les erreurs. J'ai aussi vérifié que la récompense ne récompense pas l'absurde : des heures sup avec une file vide sont moins bien notées que ne rien faire, sur 20 journées sur 20.

**5. « Comment modélisez-vous la résolution au premier contact et la satisfaction ? »**
> Chaque appel traité a une qualité de réponse, tirée des évaluations du Quality Analyst et dégradée si le conseiller n'a pas la bonne compétence ou s'il est surchargé. La probabilité de résolution en découle : 20 % pour une réponse à 40/100, environ 80 % pour une réponse moyenne. Un client non résolu peut **rappeler** plus tard, ce qui ajoute de la charge. La satisfaction, de 1 à 5, combine qualité, attente et rappel ; un abandon compte 1/5.

**6. « Vos données sont simulées : quelle est leur valeur ? »**
> Le format respecte exactement le contrat Swagger de l'équipe. Le simulateur est calibré : une journée normale occupe environ 80 % de l'équipe, et la résolution au premier contact tourne autour de 75 %, comme dans les centres réels. La limite est réelle : les chiffres absolus dépendent de ces hypothèses. En revanche, la **comparaison** entre politiques, faite sur les mêmes journées, reste valable.

**7. « Votre agent coûte plus cher en personnel : est-ce rentable ? »**
> Oui, selon la récompense définie avec les priorités métier : de +44 à +64 points de coût, contre +140 à +228 points de récompense nette. On paie un peu plus de personnel pour perdre deux à trois fois moins de clients, et l'équipe n'est plus surchargée. Si PharmaShop veut un agent plus économe, il suffit d'augmenter `cout_conseiller` dans le fichier de configuration et de réentraîner.

**8. « Votre agent est-il responsable ? Que fait-il face à une situation qu'il ne connaît pas ? »**
> Oui, grâce à quatre garde-fous (`docs/agent_responsable.md`) :
> - Il a appris les limites de ce qu'il a vécu à l'entraînement. Au-delà, il le **signale** et laisse la main aux règles du chef de plateau. Lors d'un cumul d'incidents, ce repli fait gagner 101 points par rapport au PPO seul.
> - Il **ne propose jamais d'action impossible** : on passe de 15 par jour à 0.
> - Il **propose** les dépenses (réserve, heures sup, renforts) à un superviseur, comme le demande la grille. Sans humain connecté, il agit dans un budget délégué et doit justifier les heures sup.
> - Il **explique** chaque décision dans un journal : qui a décidé, pourquoi, avec quelle confiance, validée par qui.
>
> Et ces garde-fous ne coûtent rien en performance : toujours 8 journées types sur 8 gagnées face aux règles.

**9. « Quelles sont les limites ? »**
> - Au-delà de la capacité physique du centre (volume ×3), aucune politique n'évite environ 40 % d'abandons. L'agent le détecte et le trace : la décision redevient humaine.
> - En forte affluence, il gagne moins souvent (41 journées sur 50) : même avec toutes les ressources, le centre est à la limite de sa capacité.
> - La satisfaction et la résolution au premier contact sont simulées, pas mesurées auprès de vrais clients.
> - Le Q-learning tabulaire, qui ne voit que 4 variables, décroche en situation de crise. C'est ce qui justifie PPO.

---

## 4. Chiffres à connaître par cœur

| Ce qu'on mesure | Chiffre |
|---|---|
| Taille de l'état / nombre d'actions / composantes de la récompense | **27 / 10 / 9** |
| Scénarios de la grille gagnés face aux règles | **8 sur 8** (41 à 50 journées sur 50) |
| Abandons en sous-effectif : règles → agent | 7,5 % → **2,9 %** |
| Journées inconnues où l'agent bat les règles | **92 sur 100** (p = 5·10⁻¹⁴) |
| Cas graves traités par les règles micro | **100 %** |
| Taux de réussite des explications Gemini | *à compléter après l'évaluation des 15 cas* |
| Actions impossibles par jour (PPO brut → agent responsable) | 15-20 → **0** |
| Tests automatiques | **267** |
