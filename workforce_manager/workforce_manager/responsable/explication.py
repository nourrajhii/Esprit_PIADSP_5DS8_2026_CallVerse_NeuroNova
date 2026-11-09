"""Explications lisibles des décisions de pilotage (partagées par la démo et l'agent responsable).

Ce sont des GABARITS (sans LLM) : PPO est un réseau de neurones ; ces textes décrivent la
situation observée au moment du choix, ils ne prétendent pas lire dans le réseau.
"""

import numpy as np

from workforce_manager.env.call_center_env import (
    FAMILLES_EVENEMENTS, HEURE_OUVERTURE, MAX_ATTENTE_MIN, MAX_FILE, MAX_GENERALISTES, MAX_SANTE,
    MAX_VOLUME_HEURE, MINUTES_PAR_PAS, NB_PAS, NOMS_ETAT,
)


def heure_depuis_observation(observation: np.ndarray) -> str:
    """Heure de la décision, retrouvée à partir de la tranche horaire de l'état."""
    minute = round(float(observation[NOMS_ETAT.index("tranche_horaire")]) * NB_PAS) * MINUTES_PAR_PAS
    return f"{HEURE_OUVERTURE + minute // 60:02d}h{minute % 60:02d}"


def lire_etat(observation: np.ndarray) -> dict:
    """Observation normalisée -> unités parlantes (appels, minutes, conseillers)."""
    o = dict(zip(NOMS_ETAT, observation.tolist()))
    return {
        "standard": round(o["file_standard"] * MAX_FILE["standard"]),
        "sante": round(o["file_sante"] * MAX_FILE["sante"]),
        "urgence": round(o["file_urgence"] * MAX_FILE["urgence"]),
        "attente": o["attente_moyenne"] * MAX_ATTENTE_MIN,
        "libres": round(o["conseillers_libres_generalistes"] * MAX_GENERALISTES
                        + o["conseillers_libres_sante"] * MAX_SANTE),
        "abandon_recent": o["taux_abandon_recent"],
        "alerte": o["evt_stock_sante"] > 0.5,
        "prevision": o["prevision_charge"] * MAX_VOLUME_HEURE,
        "occupation": o["taux_occupation"],
        "priorite": o["mode_priorite"] > 0.5,
        "competences": o["mode_competences"] > 0.5,
        "evenements": [nom.removeprefix("evt_").replace("_", " ") for nom in FAMILLES_EVENEMENTS if o[nom] > 0.5],
    }


def lecture_situation(action: str, e: dict) -> str:
    """Gabarit (sans LLM) : ce que montrait la situation au moment de la décision."""
    file_totale = e["standard"] + e["sante"] + e["urgence"]
    # File vide au moment d'un renfort : c'est un renfort PRÉVENTIF (avant la montée).
    if file_totale == 0:
        contexte = "aucune file pour l'instant, renfort préventif" + (" pendant l'alerte stock" if e["alerte"] else "")
    else:
        contexte = f"{file_totale} appel(s) en attente, {e['libres']} conseiller(s) libre(s)"
    textes = {
        "activer_conseiller_supplementaire": f"Un conseiller supplémentaire rejoint le plateau ({contexte}).",
        "heures_supplementaires": f"Un conseiller reste une heure de plus, coût majoré ({contexte}).",
        "planifier_renfort": f"Planning modifié : un renfort arrivera dans 30 min pour 2 h "
                             f"(prévision : {e['prevision']:.0f} appels l'heure suivante).",
        "modifier_priorites": "Priorités modifiées : les urgences et la santé passent "
                              + ("désormais en premier." if not e["priorite"] else "de nouveau dans l'ordre d'arrivée."),
        "affecter_selon_competences": "Chaque conseiller traite " + ("désormais d'abord sa spécialité "
                                      "(santé ou standard)." if not e["competences"] else "de nouveau tous les appels."),
        "affecter_conseiller_file_sante": f"File santé à {e['sante']} appel(s) : un conseiller est affecté "
                                          "à la file santé.",
        "reaffecter_conseiller_file_standard": f"File standard à {e['standard']} appel(s) : un conseiller est "
                                               "réaffecté à la file standard.",
        "reduire_effectif": f"{e['libres']} conseillers libres et peu d'attente : un conseiller "
                            "retourne en réserve pour réduire le coût.",
        "formation": "Creux d'activité : un généraliste part 30 min en formation santé "
                     "(il sera plus rapide et plus juste ensuite).",
    }
    return textes.get(action, "")


def situation(heure: str, e: dict) -> str:
    evenements = f" | ÉVÉNEMENT : {', '.join(e['evenements'])}" if e["evenements"] else ""
    return (f"{heure} | files standard {e['standard']:2d}, santé {e['sante']:2d}, urgence {e['urgence']} "
            f"| attente {e['attente']:4.1f} min | {e['libres']} libre(s) | occupation {e['occupation']:4.0%}"
            f" | prévu {e['prevision']:3.0f}/h{evenements}")
