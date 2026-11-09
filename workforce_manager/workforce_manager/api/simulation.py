"""Simulation d'une journée pour l'API : déroulé pas à pas + KPI au format Swagger.

Modèles de ce fichier = endpoint simulate-day (extension proposée à l'équipe,
voir docs/openapi_simulate_day.yaml). Le schéma Kpi, lui, est celui du contrat.
"""

from functools import lru_cache
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from workforce_manager.env.call_center_env import ACTIONS, CallCenterEnv
from workforce_manager.evaluation.run_policy import (
    DECALAGE_GRAINE_POLITIQUE, POLITIQUES, calculer_kpi, choisir_action,
)
from workforce_manager.schemas import Kpi, PerformanceProfil, ProfileType

ScenarioId = Literal["journee_normale", "sami_rupture_stock", "ines_urgence_heure_pointe", "karim_retour_sensible",
                     "sous_effectif", "incident_technique", "campagne_commerciale", "forte_affluence"]
PolicyId = Literal["none", "random", "rules", "qlearning", "ppo", "ppo_standard", "responsable"]

# Noms de l'API (anglais, comme demandé) -> noms internes des politiques.
# "ppo" = PPO GÉNÉRALISTE (journées connues + aléatoires) : choisi par défaut car plus
# régulier sur des journées inconnues (voir evaluation/generalisation.py).
# "ppo_standard" = PPO entraîné sur les 8 journées types seulement.
# "responsable" = PPO généraliste + garde-fous (situation inconnue, masquage, validation des
# actions coûteuses) + journal de chaque décision : RECOMMANDÉ (responsable/agent.py).
NOMS_INTERNES = {"none": "rien", "random": "aleatoire", "rules": "regles", "qlearning": "qlearning",
                 "ppo": "ppo_general", "ppo_standard": "ppo", "responsable": "responsable"}
POLITIQUES_ENTRAINEES = {"qlearning", "ppo", "ppo_general"}
ORDRE_PROFILS = ("calme", "impatient", "nerveux", "mecontent", "fidele", "confus", "exigeant")


class ModeleApi(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SimulateDayRequest(ModeleApi):
    scenario: ScenarioId
    policy: PolicyId
    seed: int = Field(default=0, ge=0, description="Graine de la journée (même graine = même journée).")


class SimulationStep(ModeleApi):
    pas: int
    heure: str = Field(description="Heure de fin du quart d'heure, ex. 10h15")
    action: str
    action_possible: bool
    recompense: float
    files: Dict[str, int]
    conseillers_actifs: int
    abandons_cumul: int


class SimulateDayResult(ModeleApi):
    scenario: ScenarioId
    policy: PolicyId
    seed: int
    steps: List[SimulationStep]
    kpi: Kpi
    indicateurs: Dict[str, float] = Field(description="KPI métier détaillés (abandons, SLA, coût...)")
    journal: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="policy=responsable : chaque décision (qui, quoi, pourquoi, confiance, validation)")
    journal_resume: Optional[Dict[str, int]] = None


class ModeleNonEntraine(RuntimeError):
    """Le fichier du modèle RL demandé n'existe pas encore."""


# ------------------------------------------------------------------ politiques

@lru_cache(maxsize=None)
def _politique_entrainee(nom: str):
    """Q-table / réseau PPO chargés une seule fois (sans état : partageables)."""
    try:
        return POLITIQUES[nom]()
    except FileNotFoundError as e:
        raise ModeleNonEntraine(f"Modèle '{nom}' introuvable : lancer son entraînement d'abord.") from e


def creer_politique(policy: str):
    nom = NOMS_INTERNES[policy]
    if nom in POLITIQUES_ENTRAINEES:
        return _politique_entrainee(nom)
    return POLITIQUES[nom]()        # baselines : nouvelle instance (elles ont une mémoire par journée)


# ------------------------------------------------------------------ KPI au format Swagger

def vers_kpi(info: dict) -> Kpi:
    """Info de fin de journée du simulateur -> schéma Kpi du contrat (pourcentages sur 100).

    tauxResolution = résolution au PREMIER CONTACT (FCR) ; satisfactionClient = moyenne des
    notes simulées par client (qualité, attente, rappel ; un abandon compte 1/5).
    """
    traites = info["traites"]
    profils = [PerformanceProfil(profile=p, score=round(score, 1), count=n)
               for p in ORDRE_PROFILS if p in info["qualite_par_profil"]
               for score, n in [info["qualite_par_profil"][p]]]
    return Kpi(
        qualiteReponses=round(info["qualite_moyenne"], 1),
        tauxResolution=round(100 * info["fcr"], 1),
        tempsTraitementSec=round(info["duree_traitement_moyenne_min"] * 60, 1),
        tauxEscalade=round(100 * info["escalades"] / traites, 1) if traites else 0.0,
        satisfactionClient=round(info["satisfaction_moyenne"], 2),
        performanceParProfil=profils,
    )


# ------------------------------------------------------------------ journée

def simuler_journee(scenario: str, policy: str, seed: int = 0) -> SimulateDayResult:
    """Joue une journée complète et renvoie chaque décision et les KPI finaux."""
    politique = creer_politique(policy)
    env = CallCenterEnv(scenario=scenario)
    observation, info = env.reset(seed=seed)
    politique.reset(seed + DECALAGE_GRAINE_POLITIQUE)   # même convention que l'évaluation
    steps, termine, impossibles = [], False, 0
    while not termine:
        action = choisir_action(politique, observation, env)
        observation, recompense, termine, _, info = env.step(action)
        impossibles += int(not info["action_possible"])
        steps.append(SimulationStep(
            pas=len(steps) + 1, heure=info["heure"], action=ACTIONS[action],
            action_possible=info["action_possible"], recompense=round(recompense, 2),
            files=info["files"], conseillers_actifs=info["conseillers"]["actifs"],
            abandons_cumul=info["abandons"],
        ))
    indicateurs = {k: round(float(v), 4) for k, v in calculer_kpi(info, impossibles).items()}
    journal = getattr(politique, "journal", None)
    return SimulateDayResult(scenario=scenario, policy=policy, seed=seed, steps=steps,
                             kpi=vers_kpi(info), indicateurs=indicateurs, journal=journal,
                             journal_resume=politique.resume_journal() if journal is not None else None)
