"""Entraîne un agent PPO (stable-baselines3) sur l'état complet.

Deux variantes :
- standard    : les 4 scénarios connus mélangés (étape 5) ;
- generaliste : 50 % de scénarios connus + 50 % de journées aléatoires
                (env/random_scenarios.py), pour fonctionner sur n'importe quelle journée.

Lancement (depuis le dossier parent de workforce_manager/) :
    python -m workforce_manager.policies.train_ppo                                   # standard, 300 000 pas
    python -m workforce_manager.policies.train_ppo --variante generaliste --pas 600000

Sorties (suffixe _general pour la variante généraliste) :
    policies/modeles/ppo_workforce[_general].zip      meilleur modèle (validation)
    evaluation/resultats/ppo[_general]_monitor/       récompense de chaque journée
    evaluation/resultats/ppo[_general]_validation.csv score déterministe en validation
    evaluation/figures/ppo[_general]_courbe.png       courbe d'apprentissage
"""

import argparse
import glob
import time
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from workforce_manager.env.call_center_env import NB_PAS
from workforce_manager.env.scenario_mix import ScenarioMixEnv
from workforce_manager.evaluation.validation import valider
from workforce_manager.policies.ppo import FICHIER_PPO, FICHIER_PPO_GENERAL, PPOPolicy

GRAINE = 42
NB_ENVS = 4                       # 4 journées jouées en parallèle (diversité des scénarios par lot)

# Hyperparamètres PPO, choisis pour un épisode court (48 pas) et une récompense bruitée.
HYPERPARAMETRES = dict(
    learning_rate=3e-4,           # valeur standard de PPO (Schulman et al., 2017)
    n_steps=NB_PAS * 8,           # 384 pas/env -> chaque lot = 32 journées complètes (4 envs x 8)
    batch_size=128,
    n_epochs=10,
    # gamma = 0,99 : contrairement au tabulaire, PPO estime la valeur avec un réseau et
    # GAE, ce qui supporte un horizon long ; ~100 pas couvre toute la journée (48 pas) :
    # une priorisation décidée à 10h est jugée sur ses effets jusqu'à 20h.
    gamma=0.99,
    gae_lambda=0.95,
    # Bonus d'entropie : maintient de l'exploration (7 actions, beaucoup sans effet immédiat).
    ent_coef=0.01,
    policy_kwargs=dict(net_arch=[64, 64]),   # 10 entrées : un petit réseau suffit
)
# Validation toutes les 25 000 pas (~520 journées), meilleur modèle conservé.
FREQUENCE_VALIDATION = 25_000
RACINE = Path(__file__).parent.parent


@dataclass
class Variante:
    nom: str
    part_aleatoire: float          # part des journées d'entraînement générées au hasard
    nb_aleatoires_validation: int  # journées aléatoires ajoutées aux 20 journées connues
    pas_par_defaut: int
    modele: Path

    def chemin(self, dossier: str, suffixe: str) -> Path:
        return RACINE / "evaluation" / dossier / f"{self.nom}{suffixe}"


VARIANTES = {
    "standard": Variante("ppo", 0.0, 0, 300_000, FICHIER_PPO),
    # Généraliste : 50/50 pour rester bon sur les journées connues (personas) tout en
    # apprenant à réagir à des volumes et incidents jamais vus. Plus de diversité ->
    # plus d'expérience nécessaire (600 000 pas, ~12 500 journées).
    "generaliste": Variante("ppo_general", 0.5, 20, 600_000, FICHIER_PPO_GENERAL),
}


class ValidationCallback(BaseCallback):
    """Joue le modèle courant (déterministe) sur les journées de validation, garde le meilleur."""

    def __init__(self, variante: Variante):
        super().__init__()
        self.variante = variante
        self.historique, self.meilleur, self.debut = [], -float("inf"), time.time()

    def _on_step(self) -> bool:
        if self.num_timesteps % FREQUENCE_VALIDATION < self.training_env.num_envs:
            score = valider(PPOPolicy(modele=self.model), nb_aleatoires=self.variante.nb_aleatoires_validation)
            self.historique.append({"pas": self.num_timesteps, "validation": score})
            if score > self.meilleur:
                self.meilleur = score
                self.model.save(self.variante.modele)
            print(f"pas {self.num_timesteps:7d} | validation déterministe {score:7.1f}"
                  f" | meilleure {self.meilleur:7.1f} | {time.time() - self.debut:4.0f} s", flush=True)
        return True


def creer_env(rang: int, variante: Variante, dossier_monitor: Path):
    """Fabrique l'environnement n°rang, enveloppé dans un Monitor (journal des journées)."""
    def _creer():
        env = ScenarioMixEnv(graine=GRAINE + rang, part_aleatoire=variante.part_aleatoire)
        return Monitor(env, str(dossier_monitor / f"env_{rang}"), info_keywords=("scenario",))
    return _creer


def entrainer(nb_pas: int, variante: Variante) -> ValidationCallback:
    dossier_monitor = variante.chemin("resultats", "_monitor")
    dossier_monitor.mkdir(parents=True, exist_ok=True)
    variante.modele.parent.mkdir(parents=True, exist_ok=True)
    for ancien in glob.glob(str(dossier_monitor / "*.csv")):
        Path(ancien).unlink()
    # L'état est déjà dans [0, 1] : on ne normalise que la récompense (de -60 à +15 par
    # pas selon le scénario), sinon les gradients de la fonction valeur sont instables.
    env = VecNormalize(DummyVecEnv([creer_env(i, variante, dossier_monitor) for i in range(NB_ENVS)]),
                       norm_obs=False, norm_reward=True, gamma=HYPERPARAMETRES["gamma"])
    modele = PPO("MlpPolicy", env, seed=GRAINE, device="cpu", verbose=0, **HYPERPARAMETRES)
    callback = ValidationCallback(variante)
    modele.learn(total_timesteps=nb_pas, callback=callback)
    return callback


def lire_monitor(dossier_monitor: Path) -> pd.DataFrame:
    """Rassemble les journaux Monitor, triés dans l'ordre chronologique."""
    morceaux = [pd.read_csv(f, skiprows=1) for f in sorted(glob.glob(str(dossier_monitor / "*.monitor.csv")))]
    df = pd.concat(morceaux).sort_values("t").reset_index(drop=True)
    df["pas"] = df["l"].cumsum()
    return df


def tracer_courbe(df: pd.DataFrame, validations: pd.DataFrame, chemin: Path, titre: str) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 5))
    for scenario, sous in df.groupby("scenario"):
        ax.plot(sous["pas"], sous["r"].rolling(50, min_periods=1).mean(), linewidth=1, alpha=0.5, label=scenario)
    ax.plot(df["pas"], df["r"].rolling(200, min_periods=1).mean(), color="black", linewidth=2.5,
            label="entraînement, tous scénarios (moy. glissante 200)")
    if not validations.empty:      # vide si l'entraînement est plus court qu'une période de validation
        ax.plot(validations["pas"], validations["validation"], "o-", color="crimson", linewidth=1.5,
                label="validation déterministe")
    ax.set_xlabel("pas de simulation (48 pas = 1 journée)")
    ax.set_ylabel("récompense totale de la journée")
    ax.set_title(titre)
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(chemin, dpi=120)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variante", choices=list(VARIANTES), default="standard")
    parser.add_argument("--pas", type=int, default=None)
    args = parser.parse_args()
    variante = VARIANTES[args.variante]
    nb_pas = args.pas or variante.pas_par_defaut

    debut = time.time()
    callback = entrainer(nb_pas, variante)
    validations = pd.DataFrame(callback.historique)
    validations.to_csv(variante.chemin("resultats", "_validation.csv"), index=False)
    df = lire_monitor(variante.chemin("resultats", "_monitor"))
    courbe = variante.chemin("figures", "_courbe.png")
    tracer_courbe(df, validations, courbe, f"PPO ({args.variante}) – courbe d'apprentissage")
    print(f"\n{len(df)} journées d'entraînement en {time.time() - debut:.0f} s")
    print(f"Récompense : 300 premières journées {df['r'].head(300).mean():.1f}"
          f" -> 300 dernières {df['r'].tail(300).mean():.1f}")
    print(f"Meilleure validation : {callback.meilleur:.1f} -> modèle {variante.modele}")
    print(f"Courbe : {courbe}")


if __name__ == "__main__":
    main()
