import os
from typing import Optional

import ollama
from dotenv import load_dotenv


load_dotenv()

MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
# modèle pour les messages 2, 3, 4, 5 de la conversation (vide = le même que MODEL_NAME)
MODEL_SUITE = os.getenv("OLLAMA_MODEL_SUITE") or None

# timeout : si Ollama ne répond pas en 120 s, on lève une erreur au lieu d'attendre à l'infini
_client = ollama.Client(timeout=120)


def generate_response(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.9,
    max_tokens: int = 200,
) -> str:
    """Un seul message (utilisé pour le 1er message du client)."""
    response = _client.chat(
        model=model or MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": temperature, "num_predict": max_tokens},
    )
    return response["message"]["content"]


def generate_chat(
    messages: list[dict],
    model: Optional[str] = None,
    temperature: float = 0.9,
    max_tokens: int = 200,
) -> str:
    """Tout l'historique de la conversation (utilisé pour les messages 2, 3, 4, 5)."""
    response = _client.chat(
        model=model or MODEL_SUITE or MODEL_NAME,
        messages=messages,
        # repeat_penalty : pénalise les mots déjà écrits récemment -> moins de répétitions d'un message à l'autre
        options={"temperature": temperature, "num_predict": max_tokens, "repeat_penalty": 1.15, "repeat_last_n": 256},
    )
    return response["message"]["content"]
