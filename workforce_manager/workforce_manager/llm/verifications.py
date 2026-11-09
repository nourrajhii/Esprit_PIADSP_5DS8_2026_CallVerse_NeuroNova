"""Vérifications automatiques d'une explication produite par le LLM.

Chaque vérification renvoie une liste de messages d'erreur (vide = réussie).
Utilisées à deux endroits : dans l'explainer (rejet + nouvel essai + fallback)
et dans le jeu de test (taux de réussite par vérification).
"""

import re

# Longueurs maximales (cf. prompt) : une note de supervision se lit en quelques secondes.
LONGUEUR_MIN = 15
LONGUEUR_MAX_PROBLEME = 200
LONGUEUR_MAX_DESCRIPTION = 250

# Mots qui trahissent une action : s'ils apparaissent alors que l'action n'a PAS été
# décidée, le LLM est en train d'en suggérer une nouvelle (= action inventée).
MARQUEURS_ACTION = {
    "escalade_humain": ["transférer", "transfert", "escalad", "pharmacien conseil", "conseiller humain"],
    "relancer_rag": ["relancer", "nouvelle recherche"],
    "signaler_kb": ["signaler", "équipe de la base", "mettre à jour la base", "mise à jour de la base",
                    "corriger la fiche"],
    "ajuster_reponse": ["reformuler", "reformulation", "reprendre la réponse"],
    "formation": ["formation", "former "],
}
# Une priorité moyenne/basse ne doit pas être présentée comme urgente.
MOTS_URGENCE = ["immédiat", "urgent", "sans délai", "tout de suite"]
# Dosage chiffré = conseil médical, interdit dans une note de supervision.
MOTIF_DOSAGE = re.compile(r"\d+\s*(mg|ml|g\b|comprimés?|gélules?|fois par jour)", re.IGNORECASE)

NOMS_VERIFICATIONS = ("json", "structure", "actions_inventees", "priorites", "ton_priorite",
                      "longueur", "conseil_medical")


def verifier_structure(entree: dict, sortie) -> list:
    """Même nombre de problèmes, mêmes actions (id, type, priorité) dans le même ordre."""
    if not isinstance(sortie, dict) or not isinstance(sortie.get("problems"), list) \
            or not isinstance(sortie.get("actions"), list):
        return ["format attendu : {'problems': [...], 'actions': [...]}"]
    erreurs = []
    if len(sortie["problems"]) != len(entree["constats"]):
        erreurs.append(f"{len(sortie['problems'])} problèmes au lieu de {len(entree['constats'])}")
    if not all(isinstance(p, str) for p in sortie["problems"]):
        erreurs.append("chaque problème doit être un texte")
    if len(sortie["actions"]) != len(entree["actions"]):
        erreurs.append(f"{len(sortie['actions'])} actions au lieu de {len(entree['actions'])}")
    for a in sortie["actions"]:
        if not isinstance(a, dict) or not isinstance(a.get("description"), str):
            erreurs.append("chaque action doit avoir une description texte")
            break
    return erreurs


def verifier_priorites(entree: dict, sortie: dict) -> list:
    """id, type et priorité recopiés à l'identique (le LLM ne décide rien)."""
    erreurs = []
    for attendu, recu in zip(entree["actions"], sortie["actions"]):
        for cle in ("id", "type", "priority"):
            if recu.get(cle) != attendu[cle]:
                erreurs.append(f"action {attendu['id']} : {cle} '{recu.get(cle)}' au lieu de '{attendu[cle]}'")
    return erreurs


def _textes(sortie: dict) -> list:
    return list(sortie["problems"]) + [a.get("description", "") for a in sortie["actions"]]


def verifier_actions_inventees(entree: dict, sortie: dict) -> list:
    """Aucun texte ne doit évoquer une action qui n'a pas été décidée."""
    decidees = {a["type"] for a in entree["actions"]}
    erreurs = []
    for texte in _textes(sortie):
        bas = texte.lower()
        for type_action, marqueurs in MARQUEURS_ACTION.items():
            trouve = next((m for m in marqueurs if m in bas), None)
            if type_action not in decidees and trouve:
                erreurs.append(f"évoque '{type_action}' (mot « {trouve} ») sans que l'action soit décidée")
    return erreurs


def verifier_ton_priorite(entree: dict, sortie: dict) -> list:
    """Une action moyenne ou basse ne doit pas être formulée comme urgente."""
    erreurs = []
    for attendu, recu in zip(entree["actions"], sortie["actions"]):
        if attendu["priority"] == "haute":
            continue
        mot = next((m for m in MOTS_URGENCE if m in recu.get("description", "").lower()), None)
        if mot:
            erreurs.append(f"action {attendu['id']} ({attendu['priority']}) formulée comme urgente (« {mot} »)")
    return erreurs


def verifier_longueur(entree: dict, sortie: dict) -> list:
    erreurs = []
    for p in sortie["problems"]:
        if not LONGUEUR_MIN <= len(p) <= LONGUEUR_MAX_PROBLEME:
            erreurs.append(f"problème de {len(p)} caractères (attendu {LONGUEUR_MIN}-{LONGUEUR_MAX_PROBLEME})")
    for a in sortie["actions"]:
        n = len(a.get("description", ""))
        if not LONGUEUR_MIN <= n <= LONGUEUR_MAX_DESCRIPTION:
            erreurs.append(f"description de {n} caractères (attendu {LONGUEUR_MIN}-{LONGUEUR_MAX_DESCRIPTION})")
    return erreurs


def verifier_conseil_medical(entree: dict, sortie: dict) -> list:
    return [f"dosage chiffré interdit : « {m.group(0)} »"
            for texte in _textes(sortie) for m in MOTIF_DOSAGE.finditer(texte)]


def verifier(entree: dict, sortie) -> dict:
    """Lance toutes les vérifications ; renvoie {nom: [erreurs]} (listes vides si tout va bien)."""
    resultats = {nom: [] for nom in NOMS_VERIFICATIONS}
    resultats["structure"] = verifier_structure(entree, sortie)
    if resultats["structure"]:          # inutile d'aller plus loin sur une structure fausse
        return resultats
    resultats["priorites"] = verifier_priorites(entree, sortie)
    resultats["actions_inventees"] = verifier_actions_inventees(entree, sortie)
    resultats["ton_priorite"] = verifier_ton_priorite(entree, sortie)
    resultats["longueur"] = verifier_longueur(entree, sortie)
    resultats["conseil_medical"] = verifier_conseil_medical(entree, sortie)
    return resultats


def erreurs_a_plat(resultats: dict) -> list:
    """{nom: [erreurs]} -> ["nom : erreur", ...]."""
    return [f"{nom} : {e}" for nom, erreurs in resultats.items() for e in erreurs]
