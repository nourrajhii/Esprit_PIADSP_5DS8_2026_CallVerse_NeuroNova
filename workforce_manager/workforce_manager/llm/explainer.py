"""Explications en langage naturel des décisions du Workforce Manager (Gemini).

Le LLM NE DÉCIDE PAS : il reçoit la décision déjà prise (règles de l'étape 6) et
rédige les champs "problems" et "description". Le type et la priorité de chaque
action sont toujours recopiés depuis la décision d'origine, jamais depuis le LLM.

Clé API : variable d'environnement GEMINI_API_KEY (ou GOOGLE_API_KEY), jamais dans le code.
Modèle : variable GEMINI_MODEL (défaut ci-dessous).
Si la clé manque, si l'API échoue ou si la sortie est invalide après plusieurs essais,
on renvoie les textes fixes de l'étape 6 (fallback) : l'agent répond toujours.
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol

from workforce_manager.llm.verifications import erreurs_a_plat, verifier
from workforce_manager.schemas import Action, QualityEvaluation, WorkforceDecision

journal = logging.getLogger(__name__)

DOSSIER_PROMPTS = Path(__file__).parent / "prompts"
VERSION_PROMPT = "v1"
# Version exacte (et non l'alias "gemini-flash-latest") : les résultats restent
# reproductibles tant qu'on ne change pas volontairement de modèle.
# gemini-2.5-flash n'est plus ouvert aux nouveaux comptes (404 constaté le 21/10/2026) ;
# 3.8 et 3.7-flash étaient surchargés (503) le même jour, 3.6-flash répondait en ~3 s.
# Le taux de réussite mesuré (evaluation/eval_explainer.py) vaut pour CE modèle.
MODELE_PAR_DEFAUT = "gemini-3.6-flash"
# Température basse : on veut une reformulation fidèle et stable, pas de créativité.
TEMPERATURE = 0.2
GRAINE = 42
MAX_TENTATIVES = 3            # 1 essai + 2 nouveaux essais (erreur API ou sortie invalide)
ATTENTE_BASE_S = 1.0          # attente exponentielle entre essais après une erreur API : 1 s, 2 s


class CleApiAbsente(RuntimeError):
    """Aucune clé API dans l'environnement."""


# Erreurs qui valent la peine d'un nouvel essai : quota (429) et pannes serveur (5xx).
# Les autres 4xx (clé invalide, modèle inconnu...) échoueront à l'identique : on arrête.
CODES_TEMPORAIRES = {408, 429, 500, 502, 503, 504}


# Au-delà de ce délai d'attente demandé par l'API (quota journalier épuisé), on n'insiste pas.
DELAI_MAX_REESSAI_S = 60


def delai_demande_s(erreur: Exception) -> float:
    """Délai d'attente indiqué par l'API dans un 429 (champ retryDelay, ex. '52494s'), sinon 0."""
    trouve = re.search(r"'retryDelay': '(\d+(?:\.\d+)?)s'", str(erreur))
    return float(trouve.group(1)) if trouve else 0.0


def erreur_definitive(erreur: Exception) -> bool:
    """True si réessayer est inutile : erreur client (clé, modèle...) ou quota du jour épuisé."""
    code = getattr(erreur, "code", None)
    if code == 429:
        return delai_demande_s(erreur) > DELAI_MAX_REESSAI_S
    return isinstance(code, int) and 400 <= code < 500 and code not in CODES_TEMPORAIRES


class ClientLLM(Protocol):
    """Tout client LLM : reçoit le prompt système et la conversation, renvoie un texte."""

    def generer(self, systeme: str, messages: list) -> str: ...


class GeminiClient:
    """Client Gemini (SDK google-genai), sortie JSON demandée nativement."""

    def __init__(self, modele: Optional[str] = None):
        cle = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not cle:
            raise CleApiAbsente("Définir GEMINI_API_KEY pour activer les explications LLM.")
        from google import genai   # import tardif : le reste du projet fonctionne sans le SDK
        self.client = genai.Client(api_key=cle)
        self.modele = modele or os.environ.get("GEMINI_MODEL", MODELE_PAR_DEFAUT)

    def generer(self, systeme: str, messages: list) -> str:
        from google.genai import types
        contenus = [types.Content(role=role, parts=[types.Part.from_text(text=texte)])
                    for role, texte in messages]
        reponse = self.client.models.generate_content(
            model=self.modele,
            contents=contenus,
            config=types.GenerateContentConfig(
                system_instruction=systeme,
                temperature=TEMPERATURE,
                seed=GRAINE,
                response_mime_type="application/json",
                max_output_tokens=2048,
            ),
        )
        return reponse.text or ""


@dataclass
class Explication:
    """Résultat : la décision rédigée + d'où viennent les textes (traçabilité)."""
    decision: WorkforceDecision
    source: str                       # "llm", "fallback" ou "sans_objet"
    tentatives: int = 0
    erreurs: list = field(default_factory=list)


# ------------------------------------------------------------------ prompt

def charger_prompt(version: str = VERSION_PROMPT) -> tuple:
    """Renvoie (prompt système, exemples few-shot)."""
    systeme = (DOSSIER_PROMPTS / f"explain_{version}.txt").read_text(encoding="utf-8")
    exemples = json.loads((DOSSIER_PROMPTS / f"exemples_{version}.json").read_text(encoding="utf-8"))
    return systeme, exemples


def construire_entree(decision: WorkforceDecision, evaluation: Optional[QualityEvaluation],
                      type_demande: Optional[str], profil: Optional[str], contexte: Optional[dict]) -> dict:
    """Tout ce que le LLM a le droit d'utiliser, et rien d'autre."""
    ev = evaluation.model_dump(exclude_none=True) if evaluation else {}
    ev.pop("strengths", None)                 # inutile pour expliquer un problème
    return {
        "type_demande": type_demande,
        "profil": profil,
        "contexte_centre": contexte or {},
        "evaluation": ev,
        "constats": list(decision.problems or []),
        "actions": [{"id": i, "type": a.type, "priority": a.priority, "consigne": a.description}
                    for i, a in enumerate(decision.actions or [], start=1)],
    }


def construire_messages(entree: dict, exemples: list) -> list:
    """Few-shot : (entrée, sortie attendue) pour chaque exemple, puis le cas réel."""
    messages = []
    for ex in exemples:
        messages.append(("user", json.dumps(ex["entree"], ensure_ascii=False)))
        messages.append(("model", json.dumps(ex["sortie"], ensure_ascii=False)))
    messages.append(("user", json.dumps(entree, ensure_ascii=False)))
    return messages


# ------------------------------------------------------------------ parsing

def extraire_json(texte: str) -> dict:
    """Parsing tolérant : retire les balises ```json, garde du premier '{' au dernier '}'."""
    propre = re.sub(r"```(?:json)?", "", texte or "").strip()
    debut, fin = propre.find("{"), propre.rfind("}")
    if debut == -1 or fin <= debut:
        raise ValueError("aucun objet JSON dans la réponse")
    return json.loads(propre[debut:fin + 1])


def fusionner(decision: WorkforceDecision, sortie: dict) -> WorkforceDecision:
    """Textes du LLM + type/priorité de la décision d'origine (jamais ceux du LLM)."""
    actions = [Action(type=a.type, priority=a.priority, description=s["description"].strip())
               for a, s in zip(decision.actions or [], sortie["actions"])]
    return WorkforceDecision(problems=[p.strip() for p in sortie["problems"]], actions=actions)


def message_correction(erreurs: list) -> str:
    return ("Ta réponse précédente est invalide :\n- " + "\n- ".join(erreurs[:8])
            + "\nRenvoie uniquement le JSON corrigé, en respectant toutes les règles.")


# ------------------------------------------------------------------ point d'entrée

def expliquer(decision: WorkforceDecision, evaluation: Optional[QualityEvaluation] = None,
              type_demande: Optional[str] = None, profil: Optional[str] = None,
              contexte: Optional[dict] = None, client: Optional[ClientLLM] = None,
              max_tentatives: int = MAX_TENTATIVES, attente_base: float = ATTENTE_BASE_S) -> Explication:
    """Rédige la décision avec le LLM ; en cas d'échec, renvoie les textes fixes."""
    if not decision.actions and not decision.problems:
        return Explication(decision, "sans_objet")
    if client is None:
        try:
            client = GeminiClient()
        except CleApiAbsente as e:
            return Explication(decision, "fallback", 0, [f"client : {e}"])

    systeme, exemples = charger_prompt()
    entree = construire_entree(decision, evaluation, type_demande, profil, contexte)
    messages = construire_messages(entree, exemples)
    erreurs = []
    for tentative in range(1, max_tentatives + 1):
        try:
            texte = client.generer(systeme, messages)
        except Exception as e:                                    # réseau, quota, modèle inconnu...
            erreurs.append(f"api : {type(e).__name__}: {e}")
            journal.warning("Appel LLM échoué (essai %d) : %s", tentative, e)
            if erreur_definitive(e):
                return Explication(decision, "fallback", tentative, erreurs)
            time.sleep(attente_base * 2 ** (tentative - 1))
            continue
        try:
            sortie = extraire_json(texte)
            problemes = erreurs_a_plat(verifier(entree, sortie))
        except ValueError as e:                                   # JSONDecodeError hérite de ValueError
            problemes = [f"json : {e}"]
        if not problemes:
            return Explication(fusionner(decision, sortie), "llm", tentative, erreurs)
        erreurs += problemes
        journal.info("Sortie LLM rejetée (essai %d) : %s", tentative, problemes)
        messages = messages + [("model", texte), ("user", message_correction(problemes))]
    return Explication(decision, "fallback", max_tentatives, erreurs)
