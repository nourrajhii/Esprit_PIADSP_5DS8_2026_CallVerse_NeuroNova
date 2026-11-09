"""Politique PPO entraînée (stable-baselines3), avec la même interface que les baselines."""

from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import PPO

DOSSIER_MODELES = Path(__file__).parent / "modeles"
FICHIER_PPO = DOSSIER_MODELES / "ppo_workforce.zip"
FICHIER_PPO_GENERAL = DOSSIER_MODELES / "ppo_workforce_general.zip"


class PPOPolicy:
    """Joue l'action la plus probable du réseau (mode déterministe, pas d'exploration)."""

    nom = "ppo"

    def __init__(self, chemin: Path = FICHIER_PPO, modele: PPO = None):
        self.modele = modele or PPO.load(chemin, device="cpu")

    def reset(self, graine: int = 0) -> None:
        pass

    def agir(self, observation: np.ndarray) -> int:
        action, _ = self.modele.predict(observation, deterministic=True)
        return int(action)

    def probabilites(self, observation: np.ndarray) -> np.ndarray:
        """Probabilité que la politique donne à chacune des actions (pour masquer et mesurer la confiance)."""
        obs, _ = self.modele.policy.obs_to_tensor(observation)
        with torch.no_grad():
            return self.modele.policy.get_distribution(obs).distribution.probs.cpu().numpy()[0]
