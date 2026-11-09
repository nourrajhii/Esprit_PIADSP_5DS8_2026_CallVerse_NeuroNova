"""Politique aléatoire : borne basse (« ce que ferait un pilote sans aucune logique »)."""

import numpy as np

from workforce_manager.env.call_center_env import ACTIONS


class RandomPolicy:
    """Choisit une des 7 actions au hasard, uniformément, à chaque pas."""

    nom = "aleatoire"

    def __init__(self, graine: int = 0):
        self.rng = np.random.default_rng(graine)

    def reset(self, graine: int) -> None:
        """Nouvelle journée : graine propre pour que chaque journée soit reproductible."""
        self.rng = np.random.default_rng(graine)

    def agir(self, observation: np.ndarray) -> int:
        return int(self.rng.integers(len(ACTIONS)))
