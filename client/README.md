# Client Simulator

Code du simulateur de client (modèle Ollama + prompts par profil). Il n'a plus de serveur propre :
il est servi par le serveur du dossier `../RAG` (`RAG/server.py` + `RAG/backend/core/orchestrator.py`), avec le conseiller RAG.

Test en terminal, en jouant le conseiller :

    python -m evaluation.test_conversation --profil impatient --n 3
.\.venv\Scripts\python.exe -m uvicorn server:app --port 8000        