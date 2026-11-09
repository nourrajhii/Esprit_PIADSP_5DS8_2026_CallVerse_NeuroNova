"""Tests de la comparaison statistique (fonctions pures, données synthétiques).

Lancement : python -m pytest workforce_manager/tests -v
"""

import numpy as np
import pandas as pd
import pytest

from workforce_manager.evaluation.compare_policies import (
    comparer, correction_holm, ic_bootstrap, wilcoxon_p,
)


def journees(diff_moyenne: float, n: int = 50, graine: int = 0) -> pd.DataFrame:
    """Deux politiques sur les mêmes journées : b = a + bruit + écart moyen."""
    rng = np.random.default_rng(graine)
    base = rng.normal(300, 100, n)                      # forte variabilité entre journées
    lignes = [{"scenario": "s", "graine": g, "politique": "a", "recompense_totale": base[g] + diff_moyenne
               + rng.normal(0, 10)} for g in range(n)]
    lignes += [{"scenario": "s", "graine": g, "politique": "b", "recompense_totale": base[g]} for g in range(n)]
    return pd.DataFrame(lignes)


def test_ic_bootstrap_contient_la_moyenne():
    d = np.random.default_rng(1).normal(5, 2, 50)
    bas, haut = ic_bootstrap(d, np.random.default_rng(42))
    assert bas < d.mean() < haut


def test_wilcoxon_differences_nulles():
    assert wilcoxon_p(np.zeros(20)) == 1.0


def test_appariement_detecte_un_petit_ecart():
    """+15 points malgré 100 de variabilité entre journées : l'appariement le voit."""
    r = comparer(journees(15), "a", "b", "s", "recompense_totale", np.random.default_rng(42))
    assert r["p_wilcoxon"] < 0.001 and r["ic95_bas"] > 0 and r["a_meilleur_jours"] > 40


def test_pas_d_ecart_pas_significatif():
    r = comparer(journees(0), "a", "b", "s", "recompense_totale", np.random.default_rng(42))
    assert r["p_wilcoxon"] > 0.05 and r["ic95_bas"] < 0 < r["ic95_haut"]


def test_holm():
    p = pd.Series([0.01, 0.04, 0.03, 0.20])
    ajustees = correction_holm(p)
    assert ajustees.tolist() == pytest.approx([0.04, 0.09, 0.09, 0.20])
    assert (ajustees >= p).all()
