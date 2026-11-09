"""Tests de l'étape 1 : les mocks respectent le contrat, les scénarios sont cohérents.

Lancement : python -m pytest workforce_manager/tests -v
"""

import json
from pathlib import Path

import pytest

from workforce_manager.data.generate_mocks import (
    ARCHETYPES,
    CRITERES,
    ECHELLE_MAX,
    NB_EVALUATIONS,
    generer_mocks,
)
from workforce_manager.schemas import MockEvaluationRecord, QualityEvaluation

DOSSIER_DATA = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def mocks():
    """Charge le fichier généré (il doit exister : lancer generate_mocks avant)."""
    chemin = DOSSIER_DATA / "mock_evaluations.json"
    assert chemin.exists(), "Lancer d'abord : python -m workforce_manager.data.generate_mocks"
    return json.loads(chemin.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def scenarios():
    return json.loads((DOSSIER_DATA / "scenarios.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- mocks

def test_nombre_de_mocks(mocks):
    assert len(mocks) == NB_EVALUATIONS


def test_chaque_mock_respecte_le_schema(mocks):
    for brut in mocks:
        MockEvaluationRecord.model_validate(brut)            # enveloppe interne
        QualityEvaluation.model_validate(brut["evaluation"])  # contrat Swagger strict


def test_criteres_complets_et_dans_l_echelle(mocks):
    for brut in mocks:
        criteres = brut["evaluation"]["criteria"]
        assert set(criteres) == set(CRITERES)
        assert all(0 <= v <= ECHELLE_MAX for v in criteres.values())


def test_tous_les_archetypes_sont_presents(mocks):
    assert {m["archetype"] for m in mocks} == set(ARCHETYPES)


def test_types_demande_coherents_avec_archetype(mocks):
    for m in mocks:
        if m["archetype"] == "non_conformite_sante":
            assert m["type_demande"] == "sante"
        if m["archetype"] == "urgence_mal_geree":
            assert m["type_demande"] == "urgence"


def test_generation_reproductible():
    assert generer_mocks(graine=42) == generer_mocks(graine=42)


def test_le_schema_refuse_un_champ_hors_contrat():
    with pytest.raises(ValueError):
        QualityEvaluation.model_validate({"globalScore": 80, "champInconnu": 1})


def test_le_schema_refuse_un_score_hors_bornes():
    with pytest.raises(ValueError):
        QualityEvaluation.model_validate({"globalScore": 120})


# --------------------------------------------------------------------------- scénarios

def test_scenarios_attendus(scenarios):
    ids = {s["id"] for s in scenarios["scenarios"]}
    assert ids == {"journee_normale", "sami_rupture_stock",
                   "ines_urgence_heure_pointe", "karim_retour_sensible",
                   "sous_effectif", "incident_technique", "campagne_commerciale", "forte_affluence"}


def test_scenarios_coherents(scenarios):
    nb_heures = len(scenarios["meta"]["heures"])
    for s in scenarios["scenarios"]:
        assert len(s["volume_appels_par_heure"]) == nb_heures
        assert sum(s["part_demandes"].values()) == pytest.approx(1.0)
        assert sum(s["repartition_profils"].values()) == pytest.approx(1.0)
