"""Chemins et variables d'environnement communs. Importé avant tout code qui lit os.environ."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent  # dossier RAG/ (contient .env, data/, .cache/)
load_dotenv(ROOT / ".env")

CLIENT_DIR = Path(os.getenv("CLIENT_SIM_DIR") or ROOT.parent / "client")  # code du Client Simulator
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174",
).split(",") if o.strip()]
