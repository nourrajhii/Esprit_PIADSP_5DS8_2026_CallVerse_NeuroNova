import re
from typing import Optional

from app.models import Client
from app.profiles import PROFILES


URGENCY_HINT = {
    "basse": "Ton problème n'est pas urgent.",
    "moyenne": "Ton problème est assez important.",
    "haute": "Ton problème est très urgent pour toi.",
}


def build_client_prompt(
    client: Client,
    motif: str,
    urgency: str = "moyenne",
    custom_prompt: Optional[str] = None,
) -> str:
    """Prompt pour générer UNIQUEMENT le premier message d'un client simulé."""
    profile = PROFILES[client.profil]

    prompt = f"""
Tu simules un véritable client qui appelle un centre d'appel médical.
Tu parles comme une personne au téléphone, jamais comme un assistant ou un conseiller.

IDENTITÉ DU CLIENT :
- Prénom : {client.prenom}
- Nom : {client.nom}
- Âge : {client.age}
- Ville : {client.ville}

PERSONNALITÉ DU CLIENT :
- Profil : {client.profil}
- Description : {profile["description"]}
- Traits : {", ".join(profile["traits"])}
- Style de communication : {profile["style"]}
- Réaction habituelle : {profile["reaction"]}

STYLE OBLIGATOIRE (très important) :
{profile["ton"]}

SITUATION :
Tu appelles le centre au sujet de : {motif}.
{URGENCY_HINT.get(urgency, URGENCY_HINT["moyenne"])}
"""

    if custom_prompt:
        prompt += f"Précision à respecter : {custom_prompt}\n"

    prompt += """
RÈGLES :
- C'est le tout début de l'appel : formule ta première demande au centre.
- Une ou deux phrases courtes, avec le ton de ton profil.
- N'invente pas de nom de médecin, de numéro de téléphone, d'horaire ni de diagnostic.
- N'utilise pas de phrases toutes faites.
- Ne joue jamais le rôle du conseiller.

Produis uniquement la réplique du client, sans guillemets ni préfixe.
"""
    return prompt


# le conseiller demande-t-il qui est le client ? (nom, âge, date de naissance, coordonnées...)
RE_DEMANDE_IDENTITE = re.compile(
    r"\b(nom|prénom|identité|date de naissance|né le|née le|âge|qui êtes|vous appelez|coordonnées|numéro de dossier)\b",
    re.IGNORECASE,
)


def build_turn_instruction(advisor_message: str, is_last: bool, profil: str) -> str:
    """Message envoyé au modèle après chaque réponse du conseiller (conversation enchaînée).
    Le profil est RAPPELÉ à chaque tour : sinon le modèle l'oublie et redevient poli."""
    p = PROFILES[profil]
    # rappel SANS les expressions entre « » du « ton » (sinon le modèle les recopie à chaque message)
    rappel = f"{p['description']} Traits : {', '.join(p['traits'])}. Style : {p['style']} Réaction : {p['reaction']}"
    consigne = (
        f"Le conseiller vient de te répondre :\n« {advisor_message} »\n\n"
        f"RAPPEL DE TON PROFIL ({profil}) : {rappel}\n"
        "Garde exactement ce ton dans cette réplique, même si le conseiller est aimable ou règle ton problème.\n\n"
        "Réponds-lui en restant le même client :\n"
        "- Une ou deux phrases courtes.\n"
        "- Réagis à ce qu'il vient de dire. S'il te pose une question, réponds-y.\n"
    )
    # la règle sur l'identité n'apparaît QUE si le conseiller la demande : sinon le modèle se présente à chaque message
    if RE_DEMANDE_IDENTITE.search(advisor_message):
        consigne += (
            "- Il te demande des informations sur toi : réponds avec ton identité (nom, prénom, âge, ville). "
            "Une information que tu n'as pas (date de naissance exacte, nom de ton médecin...), ne l'invente pas : dis-le à ta façon.\n"
        )
    else:
        consigne += "- Ne te présente pas : ne redonne ni ton nom, ni ton âge, ni ta ville.\n"
    consigne += (
        "- Ta réplique doit être différente de tes répliques précédentes : ne reprends pas les mêmes phrases.\n"
        "- Varie ta façon de montrer ton humeur : ne commence pas tes répliques par la même formule.\n"
        "- Ne redemande pas une information qu'il t'a déjà donnée.\n"
        "- N'invente ni nom de médecin, ni horaire, ni information qu'il n'a pas donnée.\n"
        "- Ne remercie pas à chaque réplique.\n"
    )
    if is_last:
        consigne += (
            "- C'est ta dernière réplique : termine l'appel à la manière de ton profil "
            "(un client pressé conclut sèchement, un client mécontent ne remercie pas, "
            "un client fidèle remercie chaleureusement).\n"
        )
    consigne += "\nProduis uniquement la réplique du client, sans guillemets ni préfixe."
    return consigne
