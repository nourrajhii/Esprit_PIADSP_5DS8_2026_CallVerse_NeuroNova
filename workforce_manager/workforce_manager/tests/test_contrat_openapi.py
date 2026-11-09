"""Garde-fou : nos modèles Pydantic correspondent-ils toujours au openapi.yaml de l'équipe ?

Si un membre de l'équipe modifie QualityEvaluation ou WorkforceDecision dans le
Swagger, ce test échoue et le signale immédiatement.
Chemin du contrat : variable OPENAPI_PATH, sinon ../dt-front/swagger/openapi.yaml.
"""

import os
from pathlib import Path
from typing import get_args

import pytest
import yaml

from workforce_manager.schemas import (
    Action, ActionEtendue, ActionType, Criteria, Kpi, PerformanceProfil, Priority, ProfileType,
    QualityEvaluation, WorkforceDecision, WorkforceDecisionEtendue,
)

CHEMIN_DEFAUT = Path(__file__).resolve().parents[3] / "dt-front" / "swagger" / "openapi.yaml"
CHEMIN = Path(os.environ.get("OPENAPI_PATH", CHEMIN_DEFAUT))

pytestmark = pytest.mark.skipif(not CHEMIN.exists(), reason=f"contrat introuvable : {CHEMIN}")


@pytest.fixture(scope="module")
def schemas():
    return yaml.safe_load(CHEMIN.read_text(encoding="utf-8"))["components"]["schemas"]


def test_quality_evaluation(schemas):
    swagger = schemas["QualityEvaluation"]["properties"]
    assert set(swagger) == set(QualityEvaluation.model_fields)
    assert set(swagger["criteria"]["properties"]) == set(Criteria.model_fields)
    assert (swagger["globalScore"]["minimum"], swagger["globalScore"]["maximum"]) == (0, 100)


def test_workforce_decision(schemas):
    """Accepte le contrat v1 actuel ET la v2 proposée (docs/openapi_workforce_manager_v2.yaml)."""
    swagger = schemas["WorkforceDecision"]["properties"]
    assert set(swagger) in (set(WorkforceDecision.model_fields), set(WorkforceDecisionEtendue.model_fields))
    action = swagger["actions"]["items"]["properties"]
    assert set(action) in (set(Action.model_fields), set(ActionEtendue.model_fields))
    assert set(action["type"]["enum"]) == set(get_args(ActionType))
    assert set(action["priority"]["enum"]) == set(get_args(Priority))


def test_kpi(schemas):
    swagger = schemas["Kpi"]["properties"]
    assert set(swagger) == set(Kpi.model_fields)
    assert set(swagger["performanceParProfil"]["items"]["properties"]) == set(PerformanceProfil.model_fields)


def test_profils(schemas):
    assert set(schemas["ProfileType"]["enum"]) == set(get_args(ProfileType))


def test_requete_workforce_manager():
    """Le Swagger a `evaluation` ; nos extensions optionnelles (type_demande, request, kpi) sont
    proposées dans docs/openapi_workforce_manager_v2.yaml. Si l'équipe ajoute autre chose, ce test le signale."""
    contrat = yaml.safe_load(CHEMIN.read_text(encoding="utf-8"))
    corps = contrat["paths"]["/agents/workforce-manager"]["post"]["requestBody"]["content"]
    proprietes = set(corps["application/json"]["schema"]["properties"])
    assert "evaluation" in proprietes
    assert proprietes <= {"evaluation", "type_demande", "request", "kpi"}
