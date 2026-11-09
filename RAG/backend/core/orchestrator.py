"""Orchestration : Client Simulator (dossier voisin ../client, code NON modifié) <-> agent RAG advisor (agent.py).

    client 1 -> advisor 1 -> client 2 -> advisor 2 -> ... -> client N -> advisor N      (N = 1 à 5)

Ce fichier ne contient aucune logique de simulateur : il appelle conversation.demarrer / conversation.repondre
du Client Simulator, et reçoit l'advisor en paramètre (advisor_fn) depuis server.py.

.env (facultatif) : CLIENT_SIM_DIR=C:\\chemin\\vers\\back\\client   (défaut : le dossier « client » à côté de « rag »)
"""
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from backend.settings import CLIENT_DIR
if not (CLIENT_DIR / "app").is_dir():
    raise RuntimeError(f"Client Simulator introuvable : {CLIENT_DIR / 'app'} (définis CLIENT_SIM_DIR dans .env)")
sys.path.insert(0, str(CLIENT_DIR))

from app import conversation  # noqa: E402  (code du Client Simulator)
from app.client_generator import generate_client  # noqa: E402
from app.profiles import PROFILES  # noqa: E402

# advisor_fn(message_client, historique) -> dict (AdvisorResponse) ; historique = [{"role": "client"|"advisor", "content": ...}]
AdvisorFn = Callable[[str, list[dict]], dict]

# Le simulateur a été écrit pour un centre médical, l'advisor est la parapharmacie MaPara :
# on cadre le client avec le champ « précision » existant, sans toucher à ses prompts.
CADRE = (
    "Tu écris dans le chat du service client d'une parapharmacie en ligne tunisienne (MaPara), pas à un centre médical : "
    "ne demande aucun rendez-vous médical. Si tu parles d'argent, utilise le dinar (DT), jamais l'euro."
)

# Thématiques du front (ids de TOPICS dans mock.js) -> motifs de message
MOTIFS = {
    "facturation": ["comprendre pourquoi ta dernière commande coûte plus cher que prévu (frais de livraison, de service ou de paiement)",
                    "un double débit sur ta carte pour une même commande", "obtenir la facture d'une commande"],
    "remboursement": ["un remboursement attendu depuis plusieurs jours après le retour d'un produit",
                      "retourner un produit qui ne te convient pas", "un produit reçu défectueux ou déjà ouvert"],
    "securite": ["un SMS suspect qui prétend venir du site et te demande ton code de vérification",
                 "un code de vérification (OTP) que tu n'as pas demandé", "sécuriser ton compte après une connexion bizarre"],
    "fidelite": ["les offres et packs du moment", "un avantage de fidélité ou un mois gratuit",
                 "l'authenticité et la garantie des produits vendus"],
    "technique": ["impossible d'ajouter un produit au panier", "ton paiement par carte refusé alors que tout semble correct",
                  "impossible de te connecter à ton compte"],
    "resiliation": ["résilier ton abonnement Premium", "supprimer ton compte", "arrêter les prélèvements de ton abonnement"],
    "produit": ["trouver un nettoyant visage pour peau mixte avec un budget limité en dinars",
                "un soin pour des cheveux secs et abîmés", "une crème solaire pour peau sensible",
                "un produit de soin pour bébé"],
    "soins": ["ta peau très sèche qui tiraille", "des boutons et une peau brillante : savoir quels soins choisir",
              "des pellicules ou une chute de cheveux plus forte que d'habitude", "un coup de soleil et comment protéger ta peau"],
    "bebe_maman": ["les fesses rouges de ton bébé à chaque change", "choisir des soins de toilette pour ton nouveau-né",
                   "des vergetures et la peau du ventre pendant ta grossesse", "des crevasses pendant l'allaitement"],
    "bien_etre": ["une fatigue persistante et des vitamines à choisir", "des difficultés à t'endormir le soir",
                  "des ballonnements et un transit difficile", "renforcer tes défenses avant l'hiver"],
    "precautions": ["savoir si tu peux utiliser des huiles essentielles alors que tu es enceinte",
                    "un complément alimentaire alors que tu suis déjà un traitement",
                    "quel produit choisir pour ton enfant de 3 ans", "une rougeur apparue après l'application d'un nouveau soin"],
    "choix": ["un produit en rupture de stock : trouver une alternative dans ton budget",
              "choisir un indice de protection solaire pour la plage", "comment choisir un shampoing pour ton cuir chevelu gras",
              "un cadeau pour ta mère avec un petit budget"],
    "symptome": ["un mal de dents depuis deux jours : savoir quel médecin consulter",
                 "des maux de tête fréquents : savoir vers quel spécialiste aller",
                 "une douleur persistante au dos : savoir quel médecin consulter"],
}
MOTIFS_NEUTRES = [
    "trouver un produit adapté à une peau mixte", "comprendre les frais de livraison d'une commande",
    "retourner un produit et se faire rembourser", "connaître les offres et packs du moment",
    "résoudre un problème de paiement sur le site",
]

# profils inconnus du simulateur (ex. « heureux » existe dans le front) -> profil le plus proche
PROFIL_REPLI = {"heureux": "fidele"}
LABELS = {"calme": "Calme", "impatient": "Impatient", "nerveux": "Nerveux", "mecontent": "Mécontent",
          "fidele": "Fidèle", "confus": "Confus", "exigeant": "Exigeant", "heureux": "Heureux"}
SENTIMENTS = {"calme": "neutre", "impatient": "agace", "nerveux": "anxieux", "mecontent": "negatif_fort",
              "fidele": "positif", "confus": "perdu", "exigeant": "neutre", "heureux": "tres_positif"}


def motif_pour(topic: Optional[str]) -> str:
    return random.choice(MOTIFS.get(topic or "", MOTIFS_NEUTRES))


def _precision(custom_prompt: Optional[str]) -> str:
    return CADRE + (" " + custom_prompt.strip() if custom_prompt and custom_prompt.strip() else "")


def _court(texte: str, n: int = 600) -> str:
    """Réponse de l'advisor (tableaux, liens, produits) raccourcie avant d'être donnée au client simulé."""
    t = re.sub(r"https?://\S+", "", texte)
    t = re.sub(r"[|*#_`>]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) <= n:
        return t
    cut = t[:n]
    fin = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return (cut[:fin + 1] if fin > n // 2 else cut).strip()


def _client_sim(fn, *args):
    """Appelle le Client Simulator ; toute panne (Ollama/Groq arrêté, clé manquante...) devient une RuntimeError -> 503."""
    try:
        return fn(*args)
    except Exception as e:
        raise RuntimeError(f"Client Simulator indisponible ({type(e).__name__}) : {str(e)[:200]}") from e


def _make_client(profile: str):
    sim_profile = profile if profile in PROFILES else PROFIL_REPLI.get(profile, "calme")
    client = generate_client(random.randint(1, 9999))
    client.profil = sim_profile
    return client


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def run_conversation(
    *,
    profile: str,
    topic: Optional[str],
    urgency: str,
    rag: bool,
    message_count: int,
    first_message: Optional[str],
    custom_prompt: Optional[str],
    advisor_fn: AdvisorFn,
) -> dict:
    """Joue la conversation complète ; le dict renvoyé est enregistré en base (db.py) et renvoyé au front."""
    message_count = max(1, min(5, message_count))
    client = _make_client(profile)

    t0 = time.perf_counter()
    conv = _client_sim(conversation.demarrer, client, motif_pour(topic), urgency, _precision(custom_prompt), message_count)
    getattr(conversation, "CONVERSATIONS", {}).pop(conv["id"], None)  # le simulateur garde les conversations en mémoire : on évite la fuite
    conv["createdAt"] = datetime.now(timezone.utc).isoformat()
    client_ms = _ms(t0)
    if first_message and first_message.strip():  # message saisi par l'utilisateur : il remplace celui généré
        conv["history"][0]["content"] = first_message.strip()
        conv["llm_messages"][-1]["content"] = first_message.strip()
        client_ms = 0

    turns: list[dict] = []
    history: list[dict] = []
    for i in range(message_count):
        client_msg = conv["history"][-1]["content"]
        advisor = advisor_fn(client_msg, history)
        turns.append({"turn": i + 1, "clientMessage": client_msg, "clientLatencyMs": client_ms, "advisor": advisor})
        history += [{"role": "client", "content": client_msg}, {"role": "advisor", "content": advisor["answer"]}]
        if i < message_count - 1:
            t0 = time.perf_counter()
            conv = _client_sim(conversation.repondre, conv, _court(advisor["answer"]))
            client_ms = _ms(t0)
            getattr(conversation, "CONVERSATIONS", {}).pop(conv["id"], None)

    llm = sys.modules.get("app.llm_service")
    return {
        "id": conv["id"],
        "createdAt": conv["createdAt"],
        "profile": profile,
        "topic": topic or "auto",
        "urgency": urgency,
        "rag": rag,
        "messageCount": message_count,
        "client": {"name": f"{client.prenom} {client.nom}", "age": client.age, "city": client.ville},
        "clientModel": getattr(llm, "MODEL_NAME", None),
        "advisorModel": turns[-1]["advisor"].get("model"),
        "latencyMs": sum(t["advisor"].get("latencyMs", 0) for t in turns),
        "turns": turns,
    }


def generate_first_message(*, profile: str, topic: Optional[str], urgency: str, custom_prompt: Optional[str]) -> dict:
    """Appel unitaire du Client Simulator : uniquement le premier message d'un client virtuel."""
    client = _make_client(profile)
    conv = _client_sim(conversation.demarrer, client, motif_pour(topic), urgency, _precision(custom_prompt), 1)
    getattr(conversation, "CONVERSATIONS", {}).pop(conv["id"], None)
    message = conv["history"][0]["content"]
    return {
        "agent": "Client Simulator Agent",
        "profile": profile,
        "profileLabel": LABELS.get(profile, profile),
        "topic": topic or "auto",
        "urgency": urgency,
        "message": message,
        "isConversation": False,
        "messageCount": 1,
        "conversationMessages": [message],
        "intent": topic or "demande_generale",
        "entities": {"prénom": client.prenom, "âge": str(client.age), "ville": client.ville},
        "sentiment": SENTIMENTS.get(profile, "neutre"),
        "tone": PROFILES[client.profil]["style"],
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


# --------------------------------------------------------------------------- #
# Conversation menée PAGE PAR PAGE (front : Simulateur -> Conseiller -> Simulateur -> ...)
#   1. start_session()  : 1er message du client            (POST /agents/client-simulator)
#   2. le front appelle le conseiller (POST /agents/customer-advisor, avec conversationId)
#   3. next_question()  : message suivant, qui réagit à la réponse du conseiller
#   4. save_session()   : enregistrement en base à la fin   (POST /simulations/conversation/save)
# --------------------------------------------------------------------------- #
SESSIONS: dict[str, dict] = {}  # conversationId -> état ; en mémoire (un redémarrage les efface)
MAX_SESSIONS = 200


def _payload(session: dict) -> dict:
    """Réponse du Client Simulator (même forme que generate_first_message + conversationId / turn / done)."""
    conv, client, profile, topic = session["conv"], session["client"], session["profile"], session["topic"]
    e = conversation.etat(conv)
    return {
        "agent": "Client Simulator Agent",
        "profile": profile,
        "profileLabel": LABELS.get(profile, profile),
        "topic": topic or "auto",
        "urgency": session["urgency"],
        "conversationId": e["conversationId"],
        "turn": e["turn"],
        "done": e["done"],
        "message": e["message"],
        "isConversation": True,
        "messageCount": e["messageCount"],
        "intent": topic or "demande_generale",
        "entities": {"prénom": client.prenom, "âge": str(client.age), "ville": client.ville},
        "sentiment": SENTIMENTS.get(profile, "neutre"),
        "tone": PROFILES[client.profil]["style"],
        "client": {"name": f"{client.prenom} {client.nom}", "age": client.age, "city": client.ville},
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


def start_session(*, profile: str, topic: Optional[str], urgency: str, message_count: int,
                  custom_prompt: Optional[str], rag: bool = True) -> dict:
    """Génère le 1er message du client et garde la conversation en mémoire pour la suite."""
    client = _make_client(profile)
    conv = _client_sim(conversation.demarrer, client, motif_pour(topic), urgency, _precision(custom_prompt),
                       max(1, min(5, message_count)))
    getattr(conversation, "CONVERSATIONS", {}).pop(conv["id"], None)  # on garde notre propre registre (SESSIONS)
    conv["createdAt"] = datetime.now(timezone.utc).isoformat()
    SESSIONS[conv["id"]] = {"conv": conv, "client": client, "profile": profile, "topic": topic,
                            "urgency": urgency, "rag": rag, "advisor": {}, "clientMs": {1: 0}}
    while len(SESSIONS) > MAX_SESSIONS:
        SESSIONS.pop(next(iter(SESSIONS)))  # la plus ancienne
    return _payload(SESSIONS[conv["id"]])


def next_question(conversation_id: str, advisor_message: str) -> dict:
    """Message suivant du client, après la réponse du conseiller. KeyError si la conversation est inconnue."""
    session = SESSIONS[conversation_id]
    conv = session["conv"]
    if not conversation.etat(conv)["done"]:
        t0 = time.perf_counter()
        _client_sim(conversation.repondre, conv, _court(advisor_message))
        session["clientMs"][conversation.etat(conv)["turn"]] = _ms(t0)
        getattr(conversation, "CONVERSATIONS", {}).pop(conv["id"], None)
    return _payload(session)


def remember_advisor(conversation_id: Optional[str], turn: int, advisor: dict) -> None:
    """Garde la réponse complète du conseiller (sources, modèle, étapes...) pour l'enregistrement en base."""
    if conversation_id in SESSIONS:
        SESSIONS[conversation_id]["advisor"][turn] = advisor


def session_result(conversation_id: Optional[str], *, profile: str, topic: Optional[str], rag: bool,
                   turns: list[dict], fallback_id: str) -> dict:
    """Conversation terminée au format attendu par db.save_conversation.
    turns = [{"clientMessage", "advisorAnswer"}] ; les détails du conseiller viennent de SESSIONS s'ils existent."""
    s = SESSIONS.get(conversation_id or "")
    out = []
    for i, t in enumerate(turns, start=1):
        adv = dict((s or {}).get("advisor", {}).get(i) or {})
        adv.setdefault("answer", t["advisorAnswer"])
        adv.setdefault("latencyMs", 0)
        out.append({"turn": i, "clientMessage": t["clientMessage"],
                    "clientLatencyMs": (s or {}).get("clientMs", {}).get(i, 0), "advisor": adv})
    client = s["client"] if s else None
    llm = sys.modules.get("app.llm_service")
    return {
        "id": conversation_id if s else fallback_id,
        "createdAt": s["conv"]["createdAt"] if s else datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "topic": topic or "auto",
        "urgency": s["urgency"] if s else "moyenne",
        "rag": rag,
        "messageCount": len(turns),
        "client": {"name": f"{client.prenom} {client.nom}", "age": client.age, "city": client.ville} if client else {},
        "clientModel": getattr(llm, "MODEL_NAME", None),
        "advisorModel": out[-1]["advisor"].get("model") if out else None,
        "latencyMs": sum(t["advisor"].get("latencyMs", 0) for t in out),
        "turns": out,
    }
