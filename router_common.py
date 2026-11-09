"""
Code partagé entre la construction des données, l'entraînement, l'évaluation et l'inférence du routeur LoRA.
Le prompt système est volontairement COURT : le modèle fine-tuné apprend la logique de routage
dans ses poids, pas dans un long prompt (moins de tokens = inférence plus rapide).
"""
import json
import re

BASE_MODEL_DEFAULT = "Qwen/Qwen2.5-1.5B-Instruct"

MODULES = [
    "product", "symptom",
    "facturation_frais", "remboursement_avoir", "securite_alerte_sms",
    "offres_fiabilite", "panne_acces_services", "resiliation_contrat",
]

# correspondance avec les étiquettes du fichier 07_questions_test_routage.jsonl
TEST_LABEL_MAP = {"produit_conseil": "product", "symptome_specialiste": "symptom"}

SYSTEM_PROMPT = (
    "Tu es le routeur d'un assistant de parapharmacie en ligne (MaPara Tunisie). "
    "Réponds UNIQUEMENT par un JSON de la forme "
    '{"modules": [...], "product_query": "", "symptom_query": "", "service_query": "", '
    '"urgent": false, "max_price_tnd": null}. '
    "Modules possibles : product, symptom, facturation_frais, remboursement_avoir, securite_alerte_sms, "
    "offres_fiabilite, panne_acces_services, resiliation_contrat. Liste vide pour salutations/hors-sujet."
)

KEYS = ["modules", "product_query", "symptom_query", "service_query", "urgent", "max_price_tnd"]


def build_messages(message, answer=None):
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]
    if answer is not None:
        msgs.append({"role": "assistant", "content": answer})
    return msgs


def make_target(modules, product_query="", symptom_query="", service_query="", urgent=False, max_price=None):
    return json.dumps({
        "modules": modules,
        "product_query": product_query,
        "symptom_query": symptom_query,
        "service_query": service_query,
        "urgent": urgent,
        "max_price_tnd": max_price,
    }, ensure_ascii=False)


def parse_route(text):
    """Extrait et valide le JSON généré. Renvoie un dict propre ou None si invalide."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    mods = d.get("modules")
    if not isinstance(mods, list) or any(x not in MODULES for x in mods):
        return None
    out = {"modules": list(dict.fromkeys(mods))}
    for k in ("product_query", "symptom_query", "service_query"):
        v = d.get(k, "")
        out[k] = v if isinstance(v, str) else ""
    out["urgent"] = bool(d.get("urgent", False))
    mp = d.get("max_price_tnd")
    try:
        out["max_price_tnd"] = float(mp) if mp is not None else None
    except (TypeError, ValueError):
        out["max_price_tnd"] = None
    return out
