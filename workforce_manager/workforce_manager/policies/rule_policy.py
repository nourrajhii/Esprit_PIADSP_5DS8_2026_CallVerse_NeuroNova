"""Politique « chef de plateau classique » : règles si/alors fixes et lisibles (version 2).

Elle ne voit QUE l'observation (comme l'agent RL). Une seule décision par quart d'heure,
la première règle qui s'applique gagne.
"""

import numpy as np

from workforce_manager.env.call_center_env import (
    ACTIONS, DELAI_RENFORT_PAS, DUREE_HEURES_SUP_PAS, DUREE_RENFORT_PAS, EFFECTIF_RESERVE,
    MAX_ATTENTE_MIN, MAX_FILE, MAX_GENERALISTES, MAX_HEURES_SUP, MAX_RENFORTS, MAX_SANTE,
    MAX_VOLUME_HEURE, NB_PAS, NOMS_ETAT,
)

A = {nom: num for num, nom in ACTIONS.items()}   # nom d'action -> numéro

# ---------------------------------------------------------------- seuils métier
# Renfort : 8 clients en file = 1 par conseiller actif ; au-delà, le prochain
# client attendra une durée de traitement complète (6-10 min) -> risque d'abandon.
SEUIL_FILE_RENFORT = 8
# 3 min d'attente moyenne : la patience d'un client impatient ou d'une urgence.
SEUIL_ATTENTE_RENFORT_MIN = 3.0
# 10 % d'abandons sur la dernière heure : seuil d'alerte usuel d'un plateau.
SEUIL_ABANDON_RENFORT = 0.10
# Planning : 8 conseillers traitent ~61 appels/h ; au-delà de 70 appels prévus
# l'heure suivante, le chef de plateau planifie un renfort (arrivée 30 min plus tard).
SEUIL_PREVISION_RENFORT = 70
# File santé : au-delà de 4 appels sans profil santé libre, on bascule un généraliste.
SEUIL_FILE_SANTE = 4
# File standard chargée pendant une campagne ou un incident : on y affecte un conseiller.
SEUIL_FILE_STANDARD = 6
MAX_REAFFECTATIONS = 2
# Centre calme : personne en file et au moins 3 conseillers libres.
SEUIL_LIBRES_CALME = 3
# Formation seulement le matin calme (avant 12h) : jamais pendant les pics de l'après-midi.
PAS_LIMITE_FORMATION = 16          # 16 pas après 8h = 12h00
MAX_FORMATIONS = 2


class RulePolicy:
    """Chef de plateau : organise dès l'ouverture, renforce quand ça déborde, allège quand c'est calme."""

    nom = "regles"

    def __init__(self):
        self.reset()

    def reset(self, graine: int = 0) -> None:
        """Mémoire de la journée (la graine est ignorée : politique déterministe)."""
        self.pas = 0
        self.fins_heures_sup, self.fins_renforts = [], []   # le chef de plateau connaît son planning
        self.reserve_sortie = 0
        self.reaffectations_sante = 0
        self.reaffectations_standard = 0
        self.formations = 0

    # ------------------------------------------------------------- lecture de l'état

    @staticmethod
    def lire(observation: np.ndarray) -> dict:
        """Remet l'observation normalisée dans des unités parlantes (appels, minutes...)."""
        o = dict(zip(NOMS_ETAT, observation.tolist()))
        return {
            "file_standard": o["file_standard"] * MAX_FILE["standard"],
            "file_sante": o["file_sante"] * MAX_FILE["sante"],
            "file_urgence": o["file_urgence"] * MAX_FILE["urgence"],
            "attente_min": o["attente_moyenne"] * MAX_ATTENTE_MIN,
            "libres_generalistes": o["conseillers_libres_generalistes"] * MAX_GENERALISTES,
            "libres_sante": o["conseillers_libres_sante"] * MAX_SANTE,
            "taux_abandon": o["taux_abandon_recent"],
            "prevision": o["prevision_charge"] * MAX_VOLUME_HEURE,
            "reserve": round(o["reserve_disponible"] * sum(EFFECTIF_RESERVE.values())),
            "priorite": o["mode_priorite"] > 0.5,
            "competences": o["mode_competences"] > 0.5,
            "alerte_sante": o["evt_stock_sante"] > 0.5,
            "commercial": o["evt_campagne_commerciale"] > 0.5 or o["evt_incident_technique"] > 0.5,
            "sous_effectif": o["evt_sous_effectif"] > 0.5,
        }

    # ------------------------------------------------------------- décision

    def agir(self, observation: np.ndarray) -> int:
        action = self.proposer(observation)
        self.enregistrer(action)
        return action

    def proposer(self, observation: np.ndarray) -> int:
        """Action que le chef de plateau choisirait maintenant (sans rien mémoriser)."""
        self.fins_heures_sup = [f for f in self.fins_heures_sup if f > self.pas]
        self.fins_renforts = [f for f in self.fins_renforts if f > self.pas]
        return self._decider(self.lire(observation))

    def enregistrer(self, action_executee: int) -> None:
        """Mémorise l'action RÉELLEMENT exécutée (utile quand un autre agent a décidé)."""
        self._memoriser(action_executee)
        self.pas += 1

    def _decider(self, e: dict) -> int:
        file_totale = e["file_standard"] + e["file_sante"] + e["file_urgence"]
        libres = e["libres_generalistes"] + e["libres_sante"]
        deborde = (file_totale >= SEUIL_FILE_RENFORT or e["attente_min"] >= SEUIL_ATTENTE_RENFORT_MIN
                   or e["taux_abandon"] >= SEUIL_ABANDON_RENFORT)

        # R1 - Dès l'ouverture : chaque conseiller traite d'abord sa spécialité.
        if not e["competences"]:
            return A["affecter_selon_competences"]
        # R2 - Une urgence attend ou une alerte santé tombe : urgences et santé d'abord.
        if not e["priorite"] and (e["file_urgence"] > 0 or e["alerte_sante"]):
            return A["modifier_priorites"]
        # R3 - Absences ou débordement : réserve d'abord (moins chère), heures sup ensuite.
        if (deborde or e["sous_effectif"]) and e["reserve"] > 0:
            return A["activer_conseiller_supplementaire"]
        if deborde and len(self.fins_heures_sup) < MAX_HEURES_SUP:
            return A["heures_supplementaires"]
        # R4 - Le planning annonce une forte charge : on planifie un renfort à l'avance.
        if (e["prevision"] >= SEUIL_PREVISION_RENFORT and len(self.fins_renforts) < MAX_RENFORTS
                and self.pas + DELAI_RENFORT_PAS < NB_PAS):
            return A["planifier_renfort"]
        # R5 - La file santé s'allonge sans profil santé libre : on y affecte un généraliste.
        if (e["file_sante"] >= SEUIL_FILE_SANTE and e["libres_sante"] < 1
                and self.reaffectations_sante < MAX_REAFFECTATIONS):
            return A["affecter_conseiller_file_sante"]
        # R6 - Campagne ou incident : la file standard s'allonge, on y réaffecte un conseiller.
        if (e["commercial"] and e["file_standard"] >= SEUIL_FILE_STANDARD
                and self.reaffectations_standard < MAX_REAFFECTATIONS):
            return A["reaffecter_conseiller_file_standard"]
        # R7 - Centre calme et réserve sortie : on renvoie quelqu'un en réserve.
        calme = file_totale == 0 and libres >= SEUIL_LIBRES_CALME
        if calme and self.reserve_sortie > 0 and not e["sous_effectif"]:
            return A["reduire_effectif"]
        # R8 - Calme le matin : on profite du creux pour former un généraliste.
        if (calme and self.pas < PAS_LIMITE_FORMATION and self.formations < MAX_FORMATIONS
                and e["libres_generalistes"] >= 2):
            return A["formation"]
        # R9 - Sinon on maintient l'organisation actuelle.
        return A["maintenir_organisation"]

    def _memoriser(self, action: int) -> None:
        """Le chef de plateau tient le compte de ses propres décisions."""
        nom = ACTIONS[action]
        if nom == "activer_conseiller_supplementaire":
            self.reserve_sortie += 1
        elif nom == "reduire_effectif":
            self.reserve_sortie -= 1
        elif nom == "affecter_conseiller_file_sante":
            self.reaffectations_sante += 1
        elif nom == "reaffecter_conseiller_file_standard":
            self.reaffectations_standard += 1
        elif nom == "formation":
            self.formations += 1
        elif nom == "heures_supplementaires":
            self.fins_heures_sup.append(self.pas + DUREE_HEURES_SUP_PAS)
        elif nom == "planifier_renfort":
            self.fins_renforts.append(self.pas + DELAI_RENFORT_PAS + DUREE_RENFORT_PAS)
