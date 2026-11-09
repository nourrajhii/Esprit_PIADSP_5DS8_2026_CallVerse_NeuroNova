"""Détection des situations inconnues : l'agent sait-il quand il sort de ce qu'il a appris ?

Calibrage (une fois, après l'entraînement) :
    python -m workforce_manager.responsable.domaine
On fait vivre à l'agent PPO des journées tirées comme à l'entraînement (journées types +
journées aléatoires) et on mémorise, pour chaque variable surveillée, la plus haute valeur
rencontrée (quantile 99,9 %). Explicable : « file santé 3 fois plus longue que tout ce que
l'agent a connu », plutôt qu'un score opaque.
"""

import json
from pathlib import Path
from typing import Optional

import numpy as np
import yaml

from workforce_manager.env.call_center_env import FAMILLES_EVENEMENTS, NOMS_ETAT

RACINE = Path(__file__).parent.parent
FICHIER_CONFIG = RACINE / "config" / "responsabilite.yaml"
FICHIER_DOMAINE = Path(__file__).parent / "domaine_connu.json"
NB_JOURNEES_CALIBRAGE = 400
GRAINE_CALIBRAGE = 7


def charger_config(chemin: Optional[Path] = None) -> dict:
    with open(chemin or FICHIER_CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


class DomaineConnu:
    """Bornes des situations vécues à l'entraînement et vérification d'une observation."""

    def __init__(self, bornes: dict, config: dict):
        self.bornes = bornes                     # {variable: {"bas": .., "haut": ..}}
        self.config = config["domaine_connu"]

    @classmethod
    def charger(cls, chemin: Path = FICHIER_DOMAINE, config: Optional[dict] = None) -> "DomaineConnu":
        return cls(json.loads(chemin.read_text(encoding="utf-8"))["bornes"], config or charger_config())

    def anomalies(self, observation: np.ndarray) -> list:
        """Liste lisible des raisons pour lesquelles la situation sort du domaine connu (vide = connue)."""
        o = dict(zip(NOMS_ETAT, np.asarray(observation, dtype=float)))
        raisons = []
        for nom in self.config["variables_surveillees"]:
            borne = self.bornes[nom]
            limite = borne["haut"] + self.config["marge"] * max(borne["haut"] - borne["bas"], 1e-6)
            if o[nom] > limite:
                raisons.append(f"{nom} = {o[nom]:.2f} (jamais plus de {borne['haut']:.2f} à l'entraînement)")
        simultanes = sum(o[nom] > 0.5 for nom in FAMILLES_EVENEMENTS)
        if simultanes > self.config["max_evenements_simultanes"]:
            raisons.append(f"{simultanes} événements simultanés (jamais plus de "
                           f"{self.config['max_evenements_simultanes']} à l'entraînement)")
        return raisons


# ------------------------------------------------------------------ calibrage

def collecter_observations(nb_journees: int = NB_JOURNEES_CALIBRAGE) -> np.ndarray:
    """États vécus par l'agent sur des journées tirées comme à l'entraînement."""
    from workforce_manager.env.scenario_mix import ScenarioMixEnv
    from workforce_manager.policies.ppo import FICHIER_PPO_GENERAL, PPOPolicy

    politique, env = PPOPolicy(FICHIER_PPO_GENERAL), ScenarioMixEnv(graine=GRAINE_CALIBRAGE, part_aleatoire=0.5)
    observations = []
    for _ in range(nb_journees):
        obs, _ = env.reset()
        termine = False
        while not termine:
            observations.append(obs)
            obs, _, termine, _, _ = env.step(politique.agir(obs))
    return np.array(observations)


def calibrer(nb_journees: int = NB_JOURNEES_CALIBRAGE) -> dict:
    config = charger_config()["domaine_connu"]
    obs = collecter_observations(nb_journees)
    bornes = {nom: {"bas": float(np.quantile(obs[:, i], 1 - config["quantile_haut"])),
                    "haut": float(np.quantile(obs[:, i], config["quantile_haut"]))}
              for i, nom in enumerate(NOMS_ETAT)}
    contenu = {"source": f"{nb_journees} journées (journées types + aléatoires), agent PPO généraliste",
               "nb_observations": int(len(obs)), "quantile_haut": config["quantile_haut"], "bornes": bornes}
    FICHIER_DOMAINE.write_text(json.dumps(contenu, ensure_ascii=False, indent=2), encoding="utf-8")
    return contenu


if __name__ == "__main__":
    resultat = calibrer()
    print(f"{resultat['nb_observations']} états -> {FICHIER_DOMAINE}")
    for nom in charger_config()["domaine_connu"]["variables_surveillees"]:
        print(f"  {nom:24s} haut = {resultat['bornes'][nom]['haut']:.3f}")
