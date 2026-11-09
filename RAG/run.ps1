# Lance le backend unique (Conseiller RAG + Simulateur client + Analyste Qualité) sur http://localhost:8000
# Docs : http://localhost:8000/docs   |   Santé : /api/health et /api/quality/health
Set-Location $PSScriptRoot
& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn server:app --reload --port 8000
