"""Agent responsable : le PPO entouré de quatre garde-fous, et un journal de chaque décision.

À chaque quart d'heure :
1. DÉTECTION DE L'INCONNU : si la situation sort de ce que l'agent a vécu à l'entraînement,
   il passe la main aux règles du chef de plateau (au moins 1 h) et le signale ;
2. MASQUAGE : les actions impossibles sont retirées avant le choix (jamais proposées) ;
3. VALIDATION HUMAINE : une action coûteuse est une PROPOSITION soumise au superviseur ;
   si elle est refusée, l'organisation actuelle est maintenue ;
4. JOURNAL : qui a décidé, quoi, pourquoi, avec quelle confiance, validé par qui.

Interface identique aux autres politiques : reset(graine), agir(observation, masque).
"""

from functools import lru_cache
from typing import Optional

import numpy as np

from workforce_manager.env.call_center_env import ACTIONS
from workforce_manager.policies.ppo import FICHIER_PPO_GENERAL, PPOPolicy
from workforce_manager.policies.rule_policy import RulePolicy
from workforce_manager.responsable.domaine import DomaineConnu, charger_config
from workforce_manager.responsable.explication import heure_depuis_observation, lecture_situation, lire_etat
from workforce_manager.responsable.superviseur import Proposition, SuperviseurDelegation

MAINTENIR = 0


@lru_cache(maxsize=1)
def _ia_par_defaut() -> PPOPolicy:
    """Réseau PPO chargé une seule fois (sans état : partageable entre agents)."""
    return PPOPolicy(FICHIER_PPO_GENERAL)
SOURCE_AGENT, SOURCE_REPLI = "agent PPO", "règles (repli : situation inconnue)"


class AgentResponsable:
    """PPO généraliste + détection de l'inconnu + masquage + validation humaine + journal."""

    nom = "responsable"
    accepte_masque = True          # jouer_journee lui transmet env.action_masks()

    def __init__(self, ia: Optional[PPOPolicy] = None, superviseur=None, domaine: Optional[DomaineConnu] = None,
                 config: Optional[dict] = None):
        self.config = config or charger_config()
        self.ia = ia or _ia_par_defaut()
        self.superviseur = superviseur or SuperviseurDelegation(self.config)
        self.domaine = domaine or DomaineConnu.charger(config=self.config)
        self.couts = self.config["actions_couteuses"]
        self.secours = RulePolicy()
        self.reset()

    def reset(self, graine: int = 0) -> None:
        self.secours.reset(graine)
        self.superviseur.reset()
        self.repli_restant = 0
        self.journal = []

    # ------------------------------------------------------------- décision

    def agir(self, observation: np.ndarray, masque: Optional[np.ndarray] = None) -> int:
        masque = np.ones(len(ACTIONS), dtype=bool) if masque is None else np.asarray(masque, dtype=bool)
        anomalies = self.domaine.anomalies(observation)
        if anomalies:
            self.repli_restant = self.config["domaine_connu"]["duree_repli_pas"]
        if self.repli_restant > 0:
            source, action, confiance = SOURCE_REPLI, self._action_regles(observation, masque), None
            self.repli_restant -= 1
        else:
            source = SOURCE_AGENT
            action, confiance = self._action_ia(observation, masque)
        proposee = action
        action, validation = self._valider(observation, action)
        self.secours.enregistrer(action)
        self._journaliser(observation, source, proposee, action, confiance, validation, anomalies, masque)
        return action

    def _action_ia(self, observation: np.ndarray, masque: np.ndarray) -> tuple:
        """Action la plus probable PARMI LES ACTIONS POSSIBLES, et sa probabilité renormalisée."""
        probas = self.ia.probabilites(observation) * masque
        if probas.sum() <= 0:
            return MAINTENIR, None
        probas = probas / probas.sum()
        action = int(np.argmax(probas))
        return action, float(probas[action])

    def _action_regles(self, observation: np.ndarray, masque: np.ndarray) -> int:
        action = self.secours.proposer(observation)
        return action if masque[action] else MAINTENIR

    def _valider(self, observation: np.ndarray, action: int) -> tuple:
        """Action coûteuse -> proposition au superviseur ; refusée -> on maintient l'organisation."""
        nom = ACTIONS[action]
        if nom not in self.couts:
            return action, None
        etat = lire_etat(observation)
        proposition = Proposition(heure_depuis_observation(observation), nom, self.couts[nom],
                                  lecture_situation(nom, etat), etat)
        accepte, raison = self.superviseur.valider(proposition)
        return (action if accepte else MAINTENIR), {"accepte": accepte, "par": self.superviseur.nom,
                                                    "raison": raison}

    # ------------------------------------------------------------- journal

    def _journaliser(self, observation, source, proposee, executee, confiance, validation, anomalies, masque):
        etat = lire_etat(observation)
        seuil = self.config["seuil_confiance"]
        entree = {
            "heure": heure_depuis_observation(observation),
            "source": source,
            "action_proposee": ACTIONS[proposee],
            "action_executee": ACTIONS[executee],
            "confiance": None if confiance is None else round(confiance, 3),
            "peu_sur": confiance is not None and confiance < seuil,
            "explication": lecture_situation(ACTIONS[executee], etat) or "Organisation maintenue.",
            "validation": validation,
            "situation_inconnue": anomalies,
            "actions_masquees": [ACTIONS[a] for a in range(len(ACTIONS)) if not masque[a]],
            "situation": {"files": {"standard": etat["standard"], "sante": etat["sante"], "urgence": etat["urgence"]},
                          "attente_min": round(etat["attente"], 1), "occupation": round(etat["occupation"], 2),
                          "prevision_appels_h": round(etat["prevision"]), "evenements": etat["evenements"]},
        }
        self.journal.append(entree)

    def resume_journal(self) -> dict:
        """Chiffres clés de la journée, pour un rapport ou un tableau de bord."""
        j = self.journal
        validations = [e["validation"] for e in j if e["validation"]]
        return {
            "decisions": len(j),
            "decisions_agent": sum(e["source"] == SOURCE_AGENT for e in j),
            "decisions_repli_regles": sum(e["source"] == SOURCE_REPLI for e in j),
            "propositions_couteuses": len(validations),
            "propositions_refusees": sum(not v["accepte"] for v in validations),
            "decisions_peu_sures": sum(e["peu_sur"] for e in j),
        }
