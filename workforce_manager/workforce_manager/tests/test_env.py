"""Tests de l'étape 2 : le simulateur du centre d'appels.

Lancement : python -m pytest workforce_manager/tests -v
"""

import numpy as np
import pytest

from workforce_manager.env.call_center_env import NB_PAS, CallCenterEnv


def jouer(scenario: str, graine: int = 42):
    """Joue une journée complète avec l'action 0, renvoie (nb_pas, dernière obs, info)."""
    env = CallCenterEnv(scenario=scenario)
    obs, info = env.reset(seed=graine)
    nb_pas, termine = 0, False
    while not termine:
        obs, recompense, termine, tronque, info = env.step(0)
        nb_pas += 1
        assert env.observation_space.contains(obs)
    return nb_pas, obs, info


def test_une_journee_fait_48_pas():
    nb_pas, _, _ = jouer("journee_normale")
    assert nb_pas == NB_PAS == 48


def test_bilan_coherent():
    _, _, info = jouer("journee_normale")
    en_file = sum(info["files"].values())
    assert info["traites"] + info["abandons"] + en_file == info["recus"]


def test_reproductible_avec_la_meme_graine():
    _, obs1, info1 = jouer("sami_rupture_stock", graine=7)
    _, obs2, info2 = jouer("sami_rupture_stock", graine=7)
    assert info1 == info2
    assert np.array_equal(obs1, obs2)


def test_sami_deborde_plus_que_journee_normale():
    """Le problème que l'agent devra résoudre : la rupture de stock fait exploser les abandons."""
    _, _, normal = jouer("journee_normale")
    _, _, sami = jouer("sami_rupture_stock")
    assert sami["taux_abandon"] > 2 * normal["taux_abandon"]
    assert sami["taux_abandon"] > 0.20


def test_changer_de_scenario_via_reset():
    env = CallCenterEnv()
    _, info = env.reset(seed=0, options={"scenario": "karim_retour_sensible"})
    assert info["scenario"] == "karim_retour_sensible"


def test_action_hors_espace_refusee():
    env = CallCenterEnv()
    env.reset(seed=0)
    with pytest.raises(AssertionError):
        env.step(10)


def test_render_texte():
    env = CallCenterEnv(render_mode="ansi")
    env.reset(seed=0)
    env.step(0)
    assert "files std/san/urg" in env.render()
