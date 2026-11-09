"""Politique « ne rien faire » : le centre tel qu'il fonctionne aujourd'hui (statu quo)."""

import numpy as np


class NoActionPolicy:
    """Renvoie toujours l'action 0."""

    nom = "rien"

    def reset(self, graine: int = 0) -> None:
        pass

    def agir(self, observation: np.ndarray) -> int:
        return 0
