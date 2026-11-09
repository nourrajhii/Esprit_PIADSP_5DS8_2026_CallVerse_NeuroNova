#!/usr/bin/env python3
"""
Évalue le routeur : LoRA local vs routeur LLM actuel (Groq/Gemini, celui de agent.py).

    python eval_router.py --lora models/router-lora                 # LoRA sur test (07) + validation
    python eval_router.py --lora models/router-lora --compare-llm   # compare avec le routeur LLM de agent.py
    python eval_router.py --compare-llm --no-lora                   # baseline seule : à faire AVANT de fine-tuner

Métriques : JSON valide, "module attendu ∈ modules prédits" (test 07), égalité exacte de l'ensemble de modules (validation).
Attention : la validation vient des mêmes gabarits que l'entraînement (score optimiste) ; le vrai test est 07 + tes propres questions.
"""
import argparse
import json
import time
from pathlib import Path

from router_common import TEST_LABEL_MAP, parse_route

DATA_DIR = Path("data")


def load_test():
    for p in (DATA_DIR / "modules" / "07_questions_test_routage.jsonl", DATA_DIR / "07_questions_test_routage.jsonl"):
        if p.exists():
            rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
            return [(r["question"], TEST_LABEL_MAP.get(r["module_attendu"], r["module_attendu"])) for r in rows]
    raise SystemExit("07_questions_test_routage.jsonl introuvable (data/modules/ ou data/).")


def load_val(path):
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for l in open(p, encoding="utf-8"):
        if l.strip():
            m = json.loads(l)["messages"]
            out.append((m[1]["content"], set(json.loads(m[2]["content"])["modules"])))
    return out


def llm_router():
    import agent  # le routeur LLM actuel : même prompt, même génération
    system = agent.build_router_system(list(agent.SERVICE_MODULES))

    def run(msg):
        prompt = f"HISTORIQUE:\n(vide)\n\nDERNIER MESSAGE:\n{msg}"
        try:
            d = json.loads(agent.generate(prompt, system=system, json_mode=True, temperature=0))
            return {"modules": [m for m in d.get("modules", []) if isinstance(m, str)]}
        except (json.JSONDecodeError, AttributeError, TypeError):  # JSON invalide seulement ; le quota remonte
            return None
    return run


def evaluate(name, route_fn, test, val):
    t0 = time.time()
    ok_json = hit = 0
    errors = []
    for q, expected in test:
        r = route_fn(q)
        if r is None:
            errors.append((q, expected, "JSON invalide"))
            continue
        ok_json += 1
        if expected in r["modules"]:
            hit += 1
        else:
            errors.append((q, expected, r["modules"]))
    print(f"\n=== {name} ===")
    print(f"Test 07 : {hit}/{len(test)} modules attendus retrouvés | JSON valide {ok_json}/{len(test)} | "
          f"{(time.time() - t0) / max(len(test), 1):.2f}s/question")
    for q, e, g in errors:
        print(f"  ✗ {q!r}  attendu={e}  obtenu={g}")
    if val:
        exact = 0
        for q, exp in val:
            r = route_fn(q)
            exact += bool(r) and set(r["modules"]) == exp
        print(f"Validation (gabarits, optimiste) : {exact}/{len(val)} ensembles de modules exacts")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lora", default="models/router-lora")
    ap.add_argument("--no-lora", action="store_true")
    ap.add_argument("--compare-llm", action="store_true")
    ap.add_argument("--val", default="data/finetune/router_val.jsonl")
    ap.add_argument("--val_max", type=int, default=100, help="nb max d'exemples de validation (le routeur LLM est limité par quota)")
    args = ap.parse_args()

    test = load_test()
    val = load_val(args.val)[:args.val_max]

    if not args.no_lora:
        from local_router import LocalRouter
        lr = LocalRouter(args.lora)
        evaluate("Routeur LoRA local", lambda q: lr.route(q), test, val)
    if args.compare_llm:
        evaluate("Routeur LLM (agent.py)", llm_router(), test, val)


if __name__ == "__main__":
    main()
