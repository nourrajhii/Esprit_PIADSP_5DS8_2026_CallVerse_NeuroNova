# Conformité à la grille d'évaluation – Workforce Manager (approche par Reinforcement Learning)

Ce document reprend chaque exigence de la grille et indique **où** et **comment** elle est réalisée.
Les éléments ajoutés pour coller à la grille (version 2) sont marqués **v2**.

---

## 1. Principe général et boucle d'apprentissage

| Exigence de la grille | Réalisation | Fichier |
|---|---|---|
| Piloter dynamiquement les ressources humaines tout en maîtrisant les coûts | Agent RL qui décide toutes les 15 min ; le coût des conseillers est dans la récompense | `env/call_center_env.py`, `env/reward.py` |
| Agent de Reinforcement Learning (pas seulement des règles) | Q-learning tabulaire + **PPO** (stable-baselines3) ; les règles servent de point de comparaison | `policies/` |
| Le Digital Twin est l'environnement d'apprentissage | Simulateur Gymnasium du centre PharmaShop, minute par minute | `env/call_center_env.py` |
| Boucle État St → Action At → Simulation → Récompense Rt → St+1 | `reset()` / `step(action)` renvoient l'état, la récompense et le nouvel état | `env/call_center_env.py` |
| Répéter la boucle sur un grand nombre d'épisodes | 1 épisode = 1 journée ; ~4 000 journées (Q-learning), ~6 000 et ~12 500 (PPO) | `policies/train_*.py` |
| Politique π(a\|s) qui maximise la récompense cumulée | Q-table (argmax) et réseau de politique PPO ; γ = 0,95 / 0,99 | `policies/q_learning.py`, `policies/ppo.py` |

## 2. État St – 27 variables normalisées dans [0, 1]

| Élément demandé par la grille | Variable(s) d'état |
|---|---|
| nombre de clients en attente | `clients_en_attente` **v2** |
| longueur des files d'attente | `file_standard`, `file_sante`, `file_urgence` |
| nombre de conseillers disponibles | `conseillers_libres_generalistes`, `conseillers_libres_sante` |
| nombre de conseillers occupés | `conseillers_occupes` **v2** |
| compétences disponibles | conseillers libres **par compétence** (généraliste / santé) |
| taux d'occupation des conseillers | `taux_occupation` **v2** |
| nombre de tickets en cours | = `conseillers_occupes` (un conseiller traite un appel à la fois) **v2** |
| volume de demandes entrantes | `volume_entrant_recent` (dernière heure) **v2** |
| taux d'abandon | `taux_abandon_recent` |
| temps d'attente moyen | `attente_moyenne` |
| durée moyenne des interactions (AHT) | `aht_recent` **v2** |
| taux de résolution au premier contact (FCR) | `fcr_recent` **v2** : un client mal servi peut rappeler |
| taux d'escalade | `taux_escalade_recent` **v2** |
| niveau de satisfaction client | `satisfaction_recente` **v2** (note simulée de 1 à 5 par client) |
| prévision de la charge dans les prochaines périodes | `prevision_charge` (planning de l'heure suivante) **v2** |
| événements particuliers (campagne, incident, pic…) | `evt_campagne_commerciale`, `evt_incident_technique`, `evt_pic_demande`, `evt_sous_effectif`, `evt_stock_sante` **v2** |
| *(ajouts pour que l'agent voie ses propres décisions)* | `reserve_disponible`, `mode_priorite`, `mode_competences`, `renforts_engages`, `tranche_horaire`, `score_qualite_moyen_recent` |

## 3. Actions At – 10 actions

| Action de la grille | Action de l'agent |
|---|---|
| affecter un conseiller à une file | `affecter_conseiller_file_sante` |
| réaffecter des conseillers entre différentes files | `reaffecter_conseiller_file_standard` + `affecter_conseiller_file_sante` (dans les deux sens) **v2** |
| augmenter ou réduire le nombre de conseillers affectés à une activité | `activer_conseiller_supplementaire`, `reduire_effectif` |
| modifier les priorités de traitement | `modifier_priorites` (urgence/santé d'abord ↔ ordre d'arrivée) **v2 (activable/désactivable)** |
| proposer l'activation de conseillers supplémentaires | `activer_conseiller_supplementaire` |
| proposer des heures supplémentaires | `heures_supplementaires` (coût majoré, 1 h) |
| modifier les horaires / plannings futurs | `planifier_renfort` : un conseiller arrive dans 30 min pour 2 h, au coût normal **v2** |
| affecter les conseillers selon leurs compétences | `affecter_selon_competences` (chacun traite d'abord sa spécialité) **v2** |
| décider de maintenir l'organisation actuelle | `maintenir_organisation` |
| *(ajout)* | `formation` : 30 min de formation santé, plus rapide et plus juste ensuite |

Une action impossible (plus de réserve…) ne plante jamais : elle est sans effet et légèrement pénalisée.

## 4. Fonction de récompense Rt – 9 composantes (poids justifiés dans `config/reward.yaml`)

| Objectif de la grille | Composante |
|---|---|
| amélioration du taux de résolution | `resolus` : seuls les appels **résolus au premier contact** rapportent **v2** |
| réduction du temps d'attente | `attente` (par client et par minute d'attente) |
| réduction des abandons | `abandons` (2 / 5 / 10 points selon standard / santé / urgence) |
| respect des SLA | `sla_urgence` (urgence prise en charge en moins de 3 min) |
| maintien d'un taux d'occupation raisonnable | `occupation` : pénalité hors de la plage 60-85 % **v2** |
| amélioration de la satisfaction client | `satisfaction` : (note − 3) / 2 par client servi **v2** |
| maîtrise des coûts opérationnels | `cout_conseillers`, `heures_sup` |

Le détail de chaque composante est renvoyé à chaque pas (`info["recompense_detail"]`).

## 5. Entraînement dans le Digital Twin – scénarios

| Scénario de la grille | Journée type | Mécanisme |
|---|---|---|
| Situation normale | `journee_normale` | volume stable, effectif suffisant |
| Pic d'activité | `ines_urgence_heure_pointe` (+ pics aléatoires de 8 % des quarts d'heure) | volume x1,5 à x2,2 |
| Sous-effectif | `sous_effectif` **v2** | 3 conseillers absents (non payés, indisponibles) |
| Incident technique | `incident_technique` **v2** | panne du site : x2,2 d'appels simultanés, imprévu |
| Campagne commerciale | `campagne_commerciale` **v2** | nouvelle offre : demandes commerciales x1,5, connue à l'avance |
| Période de forte affluence (anticiper) | `forte_affluence` **v2** | charge montante **annoncée par la prévision** : l'agent doit planifier des renforts |
| *(personas)* | `sami_rupture_stock`, `karim_retour_sensible` | rupture de stock, dispositif médical défectueux |
| Politiques robustes face à ces scénarios | PPO généraliste : 50 % de journées types + 50 % de **journées aléatoires** (7 types d'événements) | `env/random_scenarios.py` |

## 6. Agent responsable (au-delà de la grille)

| Garde-fou | Rôle | Mesure |
|---|---|---|
| Détection des situations inconnues | repli sur les règles du chef de plateau | 0,2 repli par jour sur les journées types, 27 sur 48 décisions lors d'un cumul d'incidents |
| Masquage des actions impossibles | l'agent ne propose que des actions réalisables | de 15-20 actions impossibles par jour à **0** |
| Validation humaine des actions coûteuses | « proposer » l'activation de conseillers, les heures sup et les renforts | environ 24 propositions par jour, dont 3 refusées (budget, ou heures sup non justifiées) |
| Journal d'explication | qui, quoi, pourquoi, confiance, validation | 48 entrées par journée, renvoyées par l'API |

Ces garde-fous **ne coûtent rien en performance** : aucun écart significatif avec le PPO brut, et toujours 8 journées types sur 8 gagnées face aux règles. Détail : `docs/agent_responsable.md`.

## 7. Résultats (version 2)

Agent PPO (modèle par défaut) face au chef de plateau, sur 50 journées identiques par scénario :

| Scénario de la grille | Abandons (règles → agent) | Journées gagnées | Significatif (Holm) |
|---|---|---|---|
| Situation normale | 6,0 % → **1,2 %** | 50/50 | p = 1·10⁻¹⁴ |
| Pic d'activité (Inès) | 8,5 % → **2,9 %** | 49/50 | p = 2·10⁻¹⁴ |
| Sous-effectif | 7,5 % → **2,9 %** | 50/50 | p = 1·10⁻¹⁴ |
| Incident technique | 10,5 % → **3,8 %** | 49/50 | p = 2·10⁻¹⁴ |
| Campagne commerciale | 7,4 % → **2,2 %** | 50/50 | p = 1·10⁻¹⁴ |
| Forte affluence | 10,8 % → **7,9 %** | 41/50 | p = 4·10⁻⁹ |

- **Robustesse** : sur 100 journées jamais vues, l'agent bat les règles 92 fois sur 100 (p = 5·10⁻¹⁴).
- **Occupation** : l'agent la maintient entre 64 et 86 % (plage raisonnable), contre 77 à 90 % pour les règles.
- **Courbes d'apprentissage** : `evaluation/figures/ppo_courbe.png` (récompense de 86 → 403) et `ppo_general_courbe.png` (de 3 → 338).

Détail : section « Résultats » du README et `evaluation/resultats/`.
