"""Q-learning tabulaire : discrétisation de l'état, agent, politique entraînée.

État discret (108 cases) = file santé x file standard x conseillers libres x tranche horaire.
"""

from pathlib import Path

import numpy as np

from workforce_manager.env.call_center_env import (
    ACTIONS, MAX_FILE, MAX_GENERALISTES, MAX_SANTE, NB_PAS, NOMS_ETAT,
)

DOSSIER_MODELES = Path(__file__).parent / "modeles"
FICHIER_Q_TABLE = DOSSIER_MODELES / "q_table.npz"

# ------------------------------------------------------------------ discrétisation
# Bornes « hautes » de chaque intervalle (inclusives). Ex. file santé : 0 | 1-3 | 4+.
# 4 appels santé en file = seuil où un profil santé seul ne suffit plus (10 min chacun).
BINS_FILE_SANTE = ("0", "1-3", "4+")
BINS_FILE_STANDARD = ("0", "1-5", "6+")      # 6+ : près du seuil de renfort (8) du chef de plateau
BINS_LIBRES = ("0", "1", "2+")
TRANCHES = ("matin", "midi", "apres-midi", "soir")   # 8-11h, 11-14h, 14-17h, 17-20h
PAS_PAR_TRANCHE = NB_PAS // len(TRANCHES)            # 12 pas = 3 heures

NB_ETATS = len(BINS_FILE_SANTE) * len(BINS_FILE_STANDARD) * len(BINS_LIBRES) * len(TRANCHES)
NB_ACTIONS = len(ACTIONS)


def _bin(valeur: int, seuils: tuple) -> int:
    """Indice de l'intervalle : seuils = bornes basses des intervalles 2, 3..."""
    return sum(valeur >= s for s in seuils)


def discretiser(observation: np.ndarray) -> int:
    """Observation continue (10 valeurs dans [0, 1]) -> numéro de case (0..107)."""
    o = dict(zip(NOMS_ETAT, np.asarray(observation, dtype=float)))
    file_sante = round(o["file_sante"] * MAX_FILE["sante"])
    file_standard = round(o["file_standard"] * MAX_FILE["standard"])
    libres = round(o["conseillers_libres_generalistes"] * MAX_GENERALISTES
                   + o["conseillers_libres_sante"] * MAX_SANTE)
    pas = round(o["tranche_horaire"] * NB_PAS)

    i_sante = _bin(file_sante, (1, 4))
    i_standard = _bin(file_standard, (1, 6))
    i_libres = _bin(libres, (1, 2))
    i_tranche = min(pas // PAS_PAR_TRANCHE, len(TRANCHES) - 1)
    return ((i_sante * len(BINS_FILE_STANDARD) + i_standard) * len(BINS_LIBRES) + i_libres) * len(TRANCHES) + i_tranche


def decrire_etat(indice: int) -> dict:
    """Numéro de case -> description lisible (pour l'analyse de la Q-table)."""
    indice, i_tranche = divmod(indice, len(TRANCHES))
    indice, i_libres = divmod(indice, len(BINS_LIBRES))
    i_sante, i_standard = divmod(indice, len(BINS_FILE_STANDARD))
    return {
        "file_sante": BINS_FILE_SANTE[i_sante],
        "file_standard": BINS_FILE_STANDARD[i_standard],
        "libres": BINS_LIBRES[i_libres],
        "tranche": TRANCHES[i_tranche],
    }


# ------------------------------------------------------------------ agent

class QLearningAgent:
    """Q(s, a) <- Q(s, a) + alpha [ r + gamma max_a' Q(s', a') - Q(s, a) ]."""

    def __init__(self, alpha: float, gamma: float, graine: int = 0, nb_etats: int = NB_ETATS):
        self.alpha = alpha
        self.gamma = gamma
        self.q = np.zeros((nb_etats, NB_ACTIONS))
        self.visites = np.zeros((nb_etats, NB_ACTIONS), dtype=int)
        self.rng = np.random.default_rng(graine)

    def choisir(self, etat: int, epsilon: float) -> int:
        """Epsilon-greedy : explore avec probabilité epsilon, sinon meilleure action connue."""
        if self.rng.random() < epsilon:
            return int(self.rng.integers(NB_ACTIONS))
        return self.meilleure_action(etat)

    def meilleure_action(self, etat: int) -> int:
        """Argmax avec départage aléatoire (au début, toutes les valeurs valent 0)."""
        valeurs = self.q[etat]
        return int(self.rng.choice(np.flatnonzero(valeurs == valeurs.max())))

    def apprendre(self, etat: int, action: int, recompense: float, etat_suivant: int, termine: bool) -> None:
        cible = recompense if termine else recompense + self.gamma * self.q[etat_suivant].max()
        self.q[etat, action] += self.alpha * (cible - self.q[etat, action])
        self.visites[etat, action] += 1

    def sauvegarder(self, chemin: Path = FICHIER_Q_TABLE, q: np.ndarray = None) -> None:
        """Sauvegarde la Q-table (par défaut l'actuelle, ou une copie retenue en validation)."""
        chemin.parent.mkdir(parents=True, exist_ok=True)
        np.savez(chemin, q=self.q if q is None else q, visites=self.visites,
                 alpha=self.alpha, gamma=self.gamma)


# ------------------------------------------------------------------ politique entraînée

class QLearningPolicy:
    """Politique gloutonne issue de la Q-table (interface identique aux baselines)."""

    nom = "qlearning"

    def __init__(self, chemin: Path = FICHIER_Q_TABLE, q: np.ndarray = None,
                 visites: np.ndarray = None, fn_discretiser=None):
        if q is None:
            donnees = np.load(chemin)
            q, visites = donnees["q"], donnees["visites"]
        self.q, self.visites = q, visites
        self.discretiser = fn_discretiser or discretiser

    def reset(self, graine: int = 0) -> None:
        pass

    def agir(self, observation: np.ndarray) -> int:
        etat = self.discretiser(observation)
        if self.visites[etat].sum() == 0:   # case jamais vue : on ne prend pas de risque
            return 0
        return int(np.argmax(self.q[etat]))
