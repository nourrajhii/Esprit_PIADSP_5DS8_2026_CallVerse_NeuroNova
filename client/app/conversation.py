"""Conversation enchaînée : client -> conseiller -> client -> ... jusqu'à `message_count` messages du client."""
import re
import uuid
from datetime import datetime

from app.llm_service import generate_chat, generate_response
from app.models import Client
from app.prompt_builder import build_client_prompt, build_turn_instruction

CONVERSATIONS: dict[str, dict] = {}

# préfixe ajouté par le modèle : « Client : », « Yassine : », « Yassine Trabelsi : »
# (un nom propre = majuscule ; un début de phrase comme « Je voudrais : » n'est pas touché)
NOMS_EXCLUS = {"Je", "Bonjour", "Écoutez", "Ecoutez", "Allô", "Allo", "Euh", "Oui", "Non", "Alors"}
RE_PREFIXE = re.compile(r"^((?i:client)|[A-ZÀ-Ý][a-zà-ÿ'-]+(?: [A-ZÀ-Ý][\w'-]+){0,2})\s*:\s+")


def nettoyer_message(texte: str) -> str:
    """Enlève les guillemets et le préfixe (« Client : », « Yassine : ») que le modèle ajoute parfois."""
    t = texte.strip().strip('"«» \n')
    m = RE_PREFIXE.match(t)
    if m and m.group(1).split()[0] not in NOMS_EXCLUS:
        t = t[m.end():]
    return t.strip('"«» \n')


def etat(conv: dict) -> dict:
    nb_client = sum(m["role"] == "client" for m in conv["history"])
    return {
        "conversationId": conv["id"],
        "message": conv["history"][-1]["content"],
        "turn": nb_client,
        "messageCount": conv["message_count"],
        "done": nb_client >= conv["message_count"],
        "history": conv["history"],
    }


def demarrer(client: Client, motif: str, urgency: str, custom_prompt, message_count: int) -> dict:
    """Génère le 1er message du client (même prompt que le fine-tuning)."""
    prompt = build_client_prompt(client, motif, urgency, custom_prompt)
    premier = nettoyer_message(generate_response(prompt))
    conv = {
        "id": str(uuid.uuid4()),
        "createdAt": datetime.now().isoformat(),
        "message_count": message_count,
        "profil": client.profil,
        "llm_messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": premier},
        ],
        "history": [{"role": "client", "content": premier, "turn": 1}],
    }
    CONVERSATIONS[conv["id"]] = conv
    return conv


def repondre(conv: dict, advisor_message: str) -> dict:
    """Ajoute la réponse du conseiller et génère le message suivant du client."""
    tour = sum(m["role"] == "client" for m in conv["history"]) + 1
    est_dernier = tour >= conv["message_count"]

    conv["llm_messages"].append({"role": "user", "content": build_turn_instruction(advisor_message, est_dernier, conv["profil"])})
    reponse = nettoyer_message(generate_chat(conv["llm_messages"]))
    conv["llm_messages"].append({"role": "assistant", "content": reponse})

    conv["history"].append({"role": "conseiller", "content": advisor_message, "turn": tour - 1})
    conv["history"].append({"role": "client", "content": reponse, "turn": tour})
    return conv
