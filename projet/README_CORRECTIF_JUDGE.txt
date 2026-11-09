CORRECTIF CIBLE — LLM-as-a-Judge pour Twinly / Quality Analyst

1. Extraire ce ZIP a la racine du projet, avec package.json.
2. Depuis la racine, lancer :
   .\quality-backend\.venv\Scripts\python.exe .\apply_llm_judge.py
3. Verifier les tests :
   cd quality-backend
   .\.venv\Scripts\python.exe -m pytest -q
4. Revenir au guide GUIDE_INSTALLATION_JUDGE.md pour variables / API / frontend.

Ce ZIP ajoute de nouveaux fichiers et un installateur. Il NE contient PAS
app.py / QualityAnalystPage.jsx / qualityClient.js en remplacement direct.
Les modifications sont effectuees par apply_llm_judge.py avec backup automatique.
Ne pas envoyer de cle Gemini dans une archive ou conversation.

Le modele de base Gemini peut renvoyer 503. Aucun resultat de benchmark du nouveau juge
n'est affirme avant execution reelle.
