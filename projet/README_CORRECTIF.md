# Correctif Quality Analyst HTTP 503

Cette livraison contient uniquement `quality-backend/app.py` et des tests supplémentaires. Elle ne modifie pas les autres agents ni React.

## Installation
1. Arrêter FastAPI avec `Ctrl + C`.
2. Sauvegarder la version existante de `quality-backend/app.py` (par exemple `app.backup.py`).
3. Remplacer seulement `quality-backend/app.py` par celui du ZIP, à partir du dossier racine du frontend.
4. Relancer les tests : `.\.venv\Scripts\python.exe -m pytest -q` depuis `quality-backend`.
5. Relancer FastAPI avec la clé GEMINI_API_KEY configurée dans le même terminal.

## Comportement
- Après une erreur 503 temporaire, la requête est retentée deux fois avec pauses progressives et jitter.
- Si les trois essais échouent, le frontend affiche une erreur claire, sans aucune fausse évaluation enregistrée.
- Un quota 429 est distinct d'un service 503 surchargé. Les tentatives supplémentaires peuvent consommer des ressources ou entraîner des coûts si elles aboutissent.
- Vérifier `GEMINI_MODEL` et utiliser un autre modèle listé, si les 503 persistent.
