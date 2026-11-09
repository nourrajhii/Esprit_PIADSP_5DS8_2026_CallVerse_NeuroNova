"""Tests de la démo (sans appel Gemini).

Lancement : python -m pytest workforce_manager/tests -v
"""

import numpy as np
import pytest

from workforce_manager import demo
from workforce_manager.env.call_center_env import ACTIONS, NOMS_ETAT
from workforce_manager.policies.ppo import FICHIER_PPO_GENERAL

pytestmark = pytest.mark.skipif(not FICHIER_PPO_GENERAL.exists(), reason="modèle PPO non entraîné")

ETAT_VIDE = {"standard": 0, "sante": 0, "urgence": 0, "attente": 0.0, "libres": 4,
             "abandon_recent": 0.0, "alerte": True, "prevision": 90.0, "occupation": 0.5,
             "priorite": False, "competences": False, "evenements": ["stock sante"]}


def test_renfort_file_vide_presente_comme_preventif():
    texte = demo.lecture_situation("activer_conseiller_supplementaire", ETAT_VIDE)
    assert "préventif" in texte and "alerte stock" in texte


def test_chaque_action_a_une_lecture():
    for num, action in ACTIONS.items():
        if num:                              # 0 = maintenir l'organisation : rien à commenter
            assert demo.lecture_situation(action, ETAT_VIDE), action


def test_lire_etat_remet_les_unites():
    obs = np.zeros(len(NOMS_ETAT), dtype=np.float32)
    obs[NOMS_ETAT.index("file_sante")] = 6 / 30            # 6 appels en file santé
    obs[NOMS_ETAT.index("evt_campagne_commerciale")] = 1.0
    etat = demo.lire_etat(obs)
    assert etat["sante"] == 6 and etat["evenements"] == ["campagne commerciale"]


@pytest.mark.parametrize("persona", ["sami", "ines", "karim"])
def test_demo_complete_sans_llm(persona, capsys):
    df = demo.demo_persona(persona, pause=0, sans_llm=True, nb_journees=1)
    sortie = capsys.readouterr().out
    assert f"APPEL DE {persona.upper()}" in sortie and "FIN DE JOURNÉE" in sortie
    assert sortie.count("Effet     :") == 12                # 12 blocs horaires de 8h à 20h
    assert set(df["politique"]) == {"Règles (avant)", "Agent responsable (après)"}
    assert "JOURNAL :" in sortie                                 # résumé des garde-fous affiché
    assert demo.FICHIER_JOURNAL.with_name(f"journal_{persona}.json").exists()
