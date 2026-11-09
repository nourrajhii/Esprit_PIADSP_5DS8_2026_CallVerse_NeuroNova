"""Compare la longueur et les défauts des messages avant / après fine-tuning (sans LLM).

python -m evaluation.comparer eval/results/reference/generations.jsonl eval/results/finetune/generations.jsonl
"""
import json
import re
import sys
from pathlib import Path

RE_MEDECIN = re.compile(r"\b(docteur|dr\.?|professeur)\s+[A-ZÀ-Ý]", re.IGNORECASE)
CONSEILLER = ["comment puis-je", "je suis là pour vous aider", "je vais vérifier", "je peux vous aider"]

for chemin in sys.argv[1:]:
    msgs = [json.loads(l)["message"] for l in Path(chemin).read_text(encoding="utf-8").splitlines() if l.strip()]
    mots = sorted(len(m.split()) for m in msgs)
    n = len(msgs)
    print(f"\n=== {chemin}")
    print(f"mots par message : moyenne {sum(mots)/n:.0f}, médiane {mots[n//2]}, max {mots[-1]}")
    print(f"plus de 40 mots         : {sum(x > 40 for x in mots)/n:.0%}")
    print(f"médecin inventé         : {sum(bool(RE_MEDECIN.search(m)) for m in msgs)/n:.0%}")
    print(f"parle comme conseiller  : {sum(any(c in m.lower() for c in CONSEILLER) for m in msgs)/n:.0%}")