# Scénario de démonstration — 3 à 5 minutes

1. **Problème** : « Je suis responsable du Quality Analyst d'un centre de relation client simulé. Ma mission : noter les réponses et signaler des risques. »
2. **Gemini principal** : bouton vert, notes et avertissements (exemple vérifié : 34/100, conformité 0 pour demande de code SMS).
3. **Qwen-LoRA** : bouton violet, classification locale CRITIQUE (fine-tuning déjà mesuré sur 14 cas synthétiques, F1 initial 0 et final 0,769).
4. **NOUVEAU LLM-as-a-Judge** : bouton « Lancer LLM-as-a-Judge ». Montre critères 0–4, citations exactes, éventuel écart avec Gemini. **Ne cite pas de métrique du nouveau juge avant d'avoir exécuté son benchmark.**
5. **Technique** : ouvre `/judge/rubric` pour montrer le contrat, la grille pondérée, les ancres 0–4 et le JSON Schema; ouvre `/docs` pour montrer l'API en tant qu'outil réutilisable. Si le backend n'est pas exposé comme outil MCP, ne prétends pas que MCP est fait.
6. **Scientifique** : affiche les résultats du benchmark (8 scénarios initiaux Gemini; nouveau benchmark du juge à générer) et les limitations : petites tailles, désaccord humain sur risque médical, dépendance de l'API, pas de validation clinique.
7. **Architecture globale** : expliquer le passage du rapport au Workforce Manager via contexte prérempli, en attendant intégration backend inter-agents.

## Réponse à la prof : pourquoi un 2e juge ?

« Gemini réalise déjà une évaluation multicritère. J'ai ajouté une contre-évaluation par un LLM-as-a-Judge séparé, avec une rubric analytique 0–4, une réponse JSON validée, des preuves textuelles contrôlées et des métriques comparées aux annotations humaines. Le juge ne reçoit pas les scores du premier modèle. L'objectif n'est pas de substituer la validation humaine mais de quantifier les désaccords et déclencher une revue en cas de risque. »

## Questions

- **Pourquoi score/4 ?** Pour rendre chaque critère explicite, ancré et facilement auditable. Score /100 = somme pondérée de chaque note ×25.
- **Pourquoi temperature 0 ?** Réduire une source de variabilité ; ne garantit pas la répétabilité parfaite d'un LLM.
- **Qu'est-ce qu'une preuve valide ?** Une citation tirée *exactement* de la réponse du conseiller et vérifiée en Python; l'interprétation peut toujours être contestée.
- **Qu'est-ce qui arrive si l'API 503 ?** 503 explicite, aucun score inventé, Qwen-LoRA indépendant de ce service.
- **Quelles garanties sur risque médical ?** Aucune certification. Garde-fou déterministe + revue humaine; risque de faux négatif du petit modèle.
