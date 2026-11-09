"""Tests de l'étape 4 : baselines et évaluation.

Lancement : python -m pytest workforce_manager/tests -v
"""

import numpy as np

from workforce_manager.env.call_center_env import ACTIONS, NOMS_ETAT
from workforce_manager.evaluation.run_policy import KPI_TABLEAU, evaluer, jouer_journee
from workforce_manager.policies.random_policy import RandomPolicy
from workforce_manager.policies.rule_policy import RulePolicy

OBS_VIDE = np.zeros(len(NOMS_ETAT), dtype=np.float32)


def test_actions_valides():
    for politique in (RandomPolicy(), RulePolicy()):
        politique.reset(0)
        for _ in range(100):
            assert politique.agir(OBS_VIDE) in ACTIONS


def test_aleatoire_reproductible():
    a, b = RandomPolicy(), RandomPolicy()
    a.reset(5)
    b.reset(5)
    assert [a.agir(OBS_VIDE) for _ in range(20)] == [b.agir(OBS_VIDE) for _ in range(20)]


A = {nom: num for num, nom in ACTIONS.items()}


def obs(**valeurs) -> np.ndarray:
    """Observation avec routage par compétences déjà actif (sinon R1 passe avant tout)."""
    o = OBS_VIDE.copy()
    o[NOMS_ETAT.index("mode_competences")] = 1.0
    for nom, v in valeurs.items():
        o[NOMS_ETAT.index(nom)] = v
    return o


def test_regle_ouverture_affecte_selon_competences():
    assert RulePolicy().agir(OBS_VIDE) == A["affecter_selon_competences"]


def test_regle_urgence_en_file_donne_priorite():
    assert RulePolicy().agir(obs(file_urgence=0.2)) == A["modifier_priorites"]   # 1 urgence en attente


def test_regle_debordement_reserve_puis_heures_sup():
    assert RulePolicy().agir(obs(file_standard=0.5, reserve_disponible=1.0)) == \
        A["activer_conseiller_supplementaire"]
    politique = RulePolicy()                      # réserve épuisée : heures sup, 2 au maximum
    actions = [politique.agir(obs(file_standard=0.5)) for _ in range(3)]
    assert actions == [A["heures_supplementaires"]] * 2 + [A["maintenir_organisation"]]


def test_regle_prevision_planifie_un_renfort():
    assert RulePolicy().agir(obs(prevision_charge=90 / 200)) == A["planifier_renfort"]


def test_regle_sous_effectif_mobilise_la_reserve():
    assert RulePolicy().agir(obs(evt_sous_effectif=1.0, reserve_disponible=1.0)) == \
        A["activer_conseiller_supplementaire"]


def test_regles_sans_action_impossible():
    for scenario in ("journee_normale", "sami_rupture_stock", "campagne_commerciale"):
        assert jouer_journee(RulePolicy(), scenario, graine=0)["actions_impossibles"] == 0


def test_kpi_dans_les_bornes():
    df = evaluer(["aleatoire", "regles"], ["sami_rupture_stock"], nb_journees=2)
    assert len(df) == 4 and set(KPI_TABLEAU) <= set(df.columns)
    for col in ("taux_abandon", "taux_abandon_sante", "respect_sla_urgence", "taux_escalade", "fcr",
                "taux_occupation"):
        assert df[col].between(0, 1).all()
    assert df["satisfaction"].between(1, 5).all()


def test_regles_meilleures_que_aleatoire_sur_sami():
    df = evaluer(["aleatoire", "regles"], ["sami_rupture_stock"], nb_journees=5)
    moyenne = df.groupby("politique")["recompense_totale"].mean()
    assert moyenne["regles"] > moyenne["aleatoire"]
