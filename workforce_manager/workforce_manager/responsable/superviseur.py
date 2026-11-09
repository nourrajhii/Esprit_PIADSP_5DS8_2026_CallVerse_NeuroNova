"""Validation humaine des actions coûteuses (« proposer » l'activation, les heures sup, un renfort).

Trois superviseurs, même interface `valider(proposition) -> (accepte, raison)` :
- SuperviseurDelegation : pas d'humain connecté ; l'agent agit dans une enveloppe
  journalière déléguée (budget) et doit justifier les heures sup ;
- SuperviseurConsole : un humain répond o/n dans le terminal (démo) ;
- SuperviseurFixe : réponse imposée (tests).
"""

from dataclasses import dataclass, field
from typing import Optional

from workforce_manager.responsable.domaine import charger_config


@dataclass
class Proposition:
    """Une action coûteuse proposée par l'agent, avec de quoi décider."""
    heure: str
    action: str
    cout_estime: float
    explication: str
    situation: dict = field(default_factory=dict)   # lecture de l'état (lire_etat)


class SuperviseurDelegation:
    """Délégation encadrée : budget journalier + justification des heures sup."""

    nom = "délégation (budget)"

    def __init__(self, config: Optional[dict] = None):
        self.config = (config or charger_config())["delegation"]
        self.reset()

    def reset(self) -> None:
        self.engage = 0.0

    def _heures_sup_justifiees(self, p: Proposition) -> bool:
        s = p.situation
        attente = s.get("standard", 0) + s.get("sante", 0) + s.get("urgence", 0)
        return (attente > 0 or bool(s.get("evenements"))
                or s.get("prevision", 0) > self.config["capacite_equipe_base_appels_h"])

    def valider(self, p: Proposition) -> tuple:
        if p.action == "heures_supplementaires" and self.config["heures_sup_si_besoin_seulement"] \
                and not self._heures_sup_justifiees(p):
            return False, "heures sup refusées : aucun client en attente, aucun événement, prévision normale"
        budget = self.config["budget_engagement_jour"]
        if self.engage + p.cout_estime > budget:
            return False, f"budget journalier délégué atteint ({self.engage:.0f}/{budget:.0f} points)"
        self.engage += p.cout_estime
        return True, f"accepté par délégation ({self.engage:.0f}/{budget:.0f} points engagés)"


class SuperviseurConsole:
    """Le chef de plateau valide lui-même les propositions (démo en direct).

    max_questions : au-delà, la délégation par budget prend le relais (une journée compte
    ~25 propositions, trop pour une démo ; 3 à 5 questions suffisent à montrer le principe).
    """

    nom = "chef de plateau (console)"

    def __init__(self, max_questions: Optional[int] = None):
        self.max_questions = max_questions
        self.delegation = SuperviseurDelegation()
        self.reset()

    def reset(self) -> None:
        self.questions = 0
        self.delegation.reset()

    def valider(self, p: Proposition) -> tuple:
        if self.max_questions is not None and self.questions >= self.max_questions:
            accepte, raison = self.delegation.valider(p)
            return accepte, f"{raison} (le chef de plateau a délégué la suite)"
        self.questions += 1
        print(f"\n  >>> PROPOSITION {p.heure} : {p.action} (coût estimé {p.cout_estime:.1f} points)")
        print(f"      {p.explication}")
        accepte = input("      Valider ? [o/n] ").strip().lower().startswith("o")
        if accepte:                      # la dépense validée compte dans l'enveloppe de la journée
            self.delegation.engage += p.cout_estime
        return accepte, "validé par le chef de plateau" if accepte else "refusé par le chef de plateau"


class SuperviseurFixe:
    """Réponse imposée (tests) ; garde la liste des propositions reçues."""

    nom = "fixe"

    def __init__(self, accepte: bool = True):
        self.accepte, self.recues = accepte, []

    def reset(self) -> None:
        self.recues = []

    def valider(self, p: Proposition) -> tuple:
        self.recues.append(p)
        return self.accepte, "accepté (test)" if self.accepte else "refusé (test)"
