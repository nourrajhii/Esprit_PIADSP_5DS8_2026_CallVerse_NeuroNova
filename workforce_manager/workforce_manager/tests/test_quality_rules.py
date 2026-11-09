"""Tests de l'étape 6 : décisions par conversation (niveau micro).

Lancement : python -m pytest workforce_manager/tests -v
"""

import json
from pathlib import Path

import pytest

from workforce_manager.micro.quality_rules import decide
from workforce_manager.schemas import MockEvaluationRecord, QualityEvaluation, WorkforceDecision

BONS_CRITERES = dict(pertinence=85, exactitude=85, groundedness=85, empathie=85, clarte=85, conformite=85)


def evaluation(score: int = 70, **criteres) -> QualityEvaluation:
    """Évaluation avec des critères bons par défaut, sauf ceux passés en paramètre."""
    return QualityEvaluation(globalScore=score, criteria={**BONS_CRITERES, **criteres})


def actions(decision: WorkforceDecision) -> dict:
    """{type: priorité} pour des assertions lisibles."""
    return {a.type: a.priority for a in decision.actions}


# --------------------------------------------------------------------------- une règle = un test

def test_groundedness_faible():
    assert actions(decide(evaluation(groundedness=45), "standard")) == {
        "relancer_rag": "haute", "signaler_kb": "haute"}


def test_exactitude_faible():
    assert actions(decide(evaluation(exactitude=50), "standard")) == {"signaler_kb": "haute"}


def test_empathie_faible():
    assert actions(decide(evaluation(empathie=50), "standard")) == {"formation": "moyenne"}


def test_conformite_faible_sur_demande_sante():
    assert actions(decide(evaluation(conformite=60), "sante")) == {"escalade_humain": "haute"}


def test_conformite_faible_sur_urgence():
    assert actions(decide(evaluation(conformite=60), "urgence")) == {"escalade_humain": "haute"}


def test_conformite_faible_sur_demande_standard_sans_escalade():
    assert actions(decide(evaluation(conformite=60), "standard")) == {"ajuster_reponse": "moyenne"}


def test_clarte_faible():
    assert actions(decide(evaluation(clarte=50), "standard")) == {"ajuster_reponse": "basse"}


def test_pertinence_faible():
    assert actions(decide(evaluation(pertinence=50), "standard")) == {"relancer_rag": "moyenne"}


def test_urgence_non_comprise_ines():
    assert actions(decide(evaluation(pertinence=40), "urgence")) == {"escalade_humain": "haute"}


def test_bonne_reponse_aucune_action():
    decision = decide(evaluation(score=88), "standard")
    assert decision.actions == [] and decision.problems == []


# --------------------------------------------------------------------------- seuils exacts

@pytest.mark.parametrize("critere, seuil", [("groundedness", 60), ("empathie", 60), ("clarte", 60)])
def test_seuil_exact_ne_declenche_pas(critere, seuil):
    assert decide(evaluation(score=79, **{critere: seuil}), "standard").actions[0].type == "ajuster_reponse"


def test_conformite_70_ne_declenche_pas():
    assert "escalade_humain" not in actions(decide(evaluation(conformite=70), "sante"))


# --------------------------------------------------------------------------- cas limites

def test_plusieurs_criteres_faibles_et_ordre_par_priorite():
    decision = decide(evaluation(score=50, empathie=40, clarte=40, conformite=30), "sante")
    assert [a.type for a in decision.actions] == ["escalade_humain", "formation", "ajuster_reponse"]
    assert len(decision.problems) == 3


def test_actions_en_double_fusionnees():
    """groundedness ET exactitude demandent signaler_kb : une seule action, deux descriptions."""
    decision = decide(evaluation(groundedness=40, exactitude=40), "standard")
    kb = [a for a in decision.actions if a.type == "signaler_kb"]
    assert len(kb) == 1 and kb[0].priority == "haute"
    assert "base contient" in kb[0].description and "corriger" in kb[0].description


def test_double_avec_priorites_differentes_garde_la_plus_haute():
    """clarté (basse) + conformité standard (moyenne) -> un seul ajuster_reponse en moyenne."""
    assert actions(decide(evaluation(clarte=40, conformite=50), "standard")) == {"ajuster_reponse": "moyenne"}


def test_garde_fou_sante_malgre_bon_score():
    assert actions(decide(evaluation(score=85, conformite=50), "sante")) == {"escalade_humain": "haute"}


def test_defaut_grave_malgre_bon_score():
    assert actions(decide(evaluation(score=85, empathie=20), "standard")) == {"formation": "moyenne"}


def test_defaut_modere_tolere_si_bon_score():
    assert decide(evaluation(score=85, empathie=50), "standard").actions == []


def test_zone_grise_score_moyen_sans_critere_faible():
    assert actions(decide(evaluation(score=72), "standard")) == {"ajuster_reponse": "basse"}


def test_criteres_partiellement_absents():
    ev = QualityEvaluation(globalScore=70, criteria={"empathie": 30})
    decision = decide(ev, "standard")
    assert actions(decision) == {"formation": "moyenne"}
    assert any("non évalués" in p and "conformite" in p for p in decision.problems)


def test_conformite_absente_sur_demande_sante_par_precaution():
    ev = QualityEvaluation(globalScore=90, criteria={"empathie": 90})
    assert actions(decide(ev, "sante")) == {"escalade_humain": "moyenne"}


def test_evaluation_vide_ne_plante_pas():
    for ev in (None, QualityEvaluation()):
        decision = decide(ev, "standard")
        assert decision.actions == []
        assert "non évalués" in decision.problems[-1]


def test_type_inconnu_traite_comme_sante():
    assert actions(decide(evaluation(conformite=50), None)) == {"escalade_humain": "haute"}


# --------------------------------------------------------------------------- schéma de sortie

def charger_mocks() -> list:
    chemin = Path(__file__).parent.parent / "data" / "mock_evaluations.json"
    return [MockEvaluationRecord.model_validate(m) for m in json.loads(chemin.read_text(encoding="utf-8"))]


def test_sortie_conforme_au_contrat_sur_les_200_mocks():
    for m in charger_mocks():
        decision = decide(m.evaluation, m.type_demande)
        brut = decision.model_dump(mode="json")
        WorkforceDecision.model_validate(brut)                       # refuse tout champ hors contrat
        assert set(brut) == {"problems", "actions"}
        for a in brut["actions"]:
            assert set(a) == {"type", "description", "priority"} and all(a.values())
        assert len({a["type"] for a in brut["actions"]}) == len(brut["actions"])   # pas de doublon


def test_coherence_avec_les_archetypes():
    """Les mocks ont une vérité terrain : les situations graves doivent toutes être traitées."""
    attendu = {"non_conformite_sante": "escalade_humain", "urgence_mal_geree": "escalade_humain",
               "groundedness_faible": "relancer_rag", "kb_manquante": "signaler_kb"}
    for m in charger_mocks():
        types = actions(decide(m.evaluation, m.type_demande))
        if m.archetype in attendu:
            assert attendu[m.archetype] in types, m.id
        if m.archetype == "bonne_reponse":
            assert "haute" not in types.values(), m.id
