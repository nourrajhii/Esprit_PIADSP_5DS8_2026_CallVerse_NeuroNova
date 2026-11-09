"""Extension du contrat : `type_demande` optionnel dans la requête du Workforce Manager.

Lancement : python -m pytest workforce_manager/tests -v
"""

import pytest

from workforce_manager.micro.quality_rules import decide
from workforce_manager.schemas import WorkforceManagerRequest

EVALUATION = {"globalScore": 70, "criteria": {"conformite": 50}}


def test_requete_strictement_conforme_au_swagger_actuel_reste_valide():
    """Rétrocompatibilité : les autres agents n'ont rien à changer."""
    requete = WorkforceManagerRequest.model_validate({"evaluation": EVALUATION})
    assert requete.type_demande is None


@pytest.mark.parametrize("type_demande", ["standard", "sante", "urgence"])
def test_requete_avec_type_demande(type_demande):
    assert WorkforceManagerRequest.model_validate(
        {"evaluation": EVALUATION, "type_demande": type_demande}).type_demande == type_demande


def test_type_demande_inconnu_refuse():
    with pytest.raises(ValueError):
        WorkforceManagerRequest.model_validate({"evaluation": EVALUATION, "type_demande": "pharmacie"})


def test_le_type_change_la_decision():
    """Même évaluation non conforme : escalade en santé, simple correction en standard."""
    def decision(type_demande):
        requete = WorkforceManagerRequest.model_validate({"evaluation": EVALUATION, "type_demande": type_demande})
        return {a.type for a in decide(requete.evaluation, requete.type_demande).actions}

    assert "escalade_humain" in decision("sante")
    assert "escalade_humain" not in decision("standard")
    assert "escalade_humain" in decision(None)       # absent -> principe de précaution
