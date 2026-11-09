QUALITY ANALYST — AUDIT DES ERREURS / OCTOBRE 2026

Ce kit ne modifie pas Twinly, FastAPI, SQLite ni les annotations.

1. Décompresse le ZIP dans le dossier quality-backend.
2. Dans PowerShell, depuis quality-backend :
   .\.venv\Scripts\python.exe .\analyser_ecosante.py
3. Lis les 5 plus grands écarts affichés.
4. Ouvre datasets\audit_ecosante.csv dans Excel.

Pour conserver la reproductibilité, sauvegarde les versions du modèle, du prompt,
des annotations et du jeu de test. Evite de modifier les annotations en fonction
des résultats IA, et demande une seconde annotation indépendante.

IMPORTANT : la détection de secrets de ton backend comporte une règle déterministe ;
son F1 mesure une chaîne hybride. Le cas médical dangereux ECOSANTE-06 n'a pas
encore de prédiction Gemini et ne peut pas valider le rappel médical.
