"""Tests de la déduction du type de demande depuis la requête client.

Lancement : python -m pytest workforce_manager/tests -v
"""

import pytest

from workforce_manager.micro.type_demande import deduire_type_demande
from workforce_manager.schemas import RequeteClient


@pytest.mark.parametrize("message, attendu", [
    ("Mes capteurs de GLYCÉMIE ne sont pas livrés", "sante"),
    ("Quelle est la posologie de ce médicament ?", "sante"),
    ("Mon tensiomètre affiche des valeurs fausses", "sante"),
    ("Mon enfant a avalé un médicament, c'est urgent !", "urgence"),   # urgence prime sur santé
    ("Je veux suivre ma commande", "standard"),
])
def test_mots_cles_du_message(message, attendu):
    assert deduire_type_demande(None, RequeteClient(message=message))[0] == attendu


def test_explicite_prioritaire():
    assert deduire_type_demande("standard", RequeteClient(message="urgence")) == ("standard", "type_demande")


def test_entites_avant_mots_cles():
    requete = RequeteClient(message="suivi de colis", entities={"type_demande": "urgence"})
    assert deduire_type_demande(None, requete) == ("urgence", "request.entities")


def test_entite_invalide_ignoree():
    requete = RequeteClient(message="ordonnance", entities={"type_demande": "pharmacie"})
    assert deduire_type_demande(None, requete) == ("sante", "request.message")


@pytest.mark.parametrize("requete", [None, RequeteClient(), RequeteClient(profile="calme")])
def test_rien_d_exploitable_donne_inconnu(requete):
    assert deduire_type_demande(None, requete) == (None, "inconnu")


@pytest.mark.parametrize("requete", [None, RequeteClient(message="colis"), RequeteClient(message="ordonnance"),
                                     RequeteClient(entities={"type_demande": "sante"})])
def test_provenance_ascii_pour_en_tete_http(requete):
    """La provenance part dans l'en-tête X-Type-Demande-Source : ASCII obligatoire."""
    assert deduire_type_demande(None, requete)[1].isascii()
