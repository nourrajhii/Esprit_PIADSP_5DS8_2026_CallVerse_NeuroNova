"""Historique des simulations globales (liste du front + détail), persisté dans .cache/simulations.json."""
import json
import threading
from typing import Optional

from backend.settings import ROOT

FILE = ROOT / ".cache" / "simulations.json"
_lock = threading.Lock()


def _load() -> list[dict]:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def add(result: dict) -> None:
    """Ajoute (ou remplace, à id égal) une simulation ; la plus récente en premier."""
    with _lock:
        items = [r for r in _load() if r.get("id") != result["id"]]
        FILE.parent.mkdir(parents=True, exist_ok=True)
        FILE.write_text(json.dumps([result] + items, ensure_ascii=False, indent=1), encoding="utf-8")


def get(sim_id: str) -> Optional[dict]:
    return next((r for r in _load() if r.get("id") == sim_id), None)


def summaries() -> list[dict]:
    """Lignes de l'historique (id, title, profile, score, createdAt)."""
    return [{k: r.get(k) for k in ("id", "title", "profile", "score", "createdAt")} for r in _load()]
