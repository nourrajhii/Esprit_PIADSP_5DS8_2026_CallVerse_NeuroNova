"""Déduire le type de demande (standard / sante / urgence) d'une requête client.

Ordre de priorité, du plus fiable au moins fiable :
1. `type_demande` envoyé explicitement dans la requête du Workforce Manager ;
2. `request.entities["type_demande"]` (renseigné par le Client Simulator) ;
3. mots-clés dans `request.intent` puis `request.message` ;
4. rien d'exploitable -> None (l'agent applique alors le principe de précaution santé).

Les mots-clés penchent volontairement vers « santé » : chez PharmaShop, traiter à tort une
demande standard comme santé coûte une escalade inutile ; l'inverse peut exposer un patient.
"""

import unicodedata
from typing import Optional, Tuple

TYPES_VALIDES = ("standard", "sante", "urgence")

# L'urgence est testée en premier : « urgence pour mon enfant qui a avalé un médicament »
# contient aussi un mot santé, mais doit être traitée comme une urgence.
MOTS_URGENCE = ("urgence", "urgent", "samu", "intoxication", "avale", "ingere", "malaise",
                "etouffe", "convulsion", "inconscient", "fievre forte", "detresse")
MOTS_SANTE = ("sante", "medicament", "posologie", "ordonnance", "pharmac", "tensiometre",
              "glycemie", "diabet", "insuline", "dispositif medical", "effet secondaire",
              "allergie", "traitement", "contre-indication", "notice", "dosage", "capteur")


def _normaliser(texte: str) -> str:
    """Minuscules sans accents : « Glycémie » et « glycemie » se comparent pareil."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return sans_accents.lower().replace("_", " ")


def _depuis_texte(texte: Optional[str]) -> Optional[str]:
    if not texte:
        return None
    t = _normaliser(texte)
    if any(m in t for m in MOTS_URGENCE):
        return "urgence"
    if any(m in t for m in MOTS_SANTE):
        return "sante"
    return None


def deduire_type_demande(type_explicite: Optional[str], requete_client) -> Tuple[Optional[str], str]:
    """Renvoie (type_demande, provenance) ; provenance sert à tracer la décision."""
    if type_explicite:
        return type_explicite, "type_demande"
    if requete_client is None:
        return None, "inconnu"
    entites = requete_client.entities or {}
    if entites.get("type_demande") in TYPES_VALIDES:
        return entites["type_demande"], "request.entities"
    for champ in ("intent", "message"):
        trouve = _depuis_texte(getattr(requete_client, champ, None))
        if trouve:
            return trouve, f"request.{champ}"
    # Une intention ou un message sans aucun mot santé/urgence : demande standard.
    # (Provenance en ASCII : elle est renvoyée dans un en-tête HTTP, qui refuse les accents.)
    if requete_client.intent or requete_client.message:
        return "standard", "request.sans_mot_cle"
    return None, "inconnu"
