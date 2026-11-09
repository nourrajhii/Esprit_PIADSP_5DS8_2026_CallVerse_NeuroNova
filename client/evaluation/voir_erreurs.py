"""Affiche les messages mal reconnus par le juge, pour un profil donné.

python -m evaluation.voir_erreurs --details eval/results/qwen2.5-3b/profil_details.jsonl --profil mecontent
"""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--details", required=True)
parser.add_argument("--profil", default=None, help="vide = tous les profils")
args = parser.parse_args()

lignes = [json.loads(l) for l in Path(args.details).read_text(encoding="utf-8").splitlines() if l.strip()]
erreurs = [r for r in lignes if r["predit"] != r["profil"] and (args.profil is None or r["profil"] == args.profil)]

print(f"{len(erreurs)} erreurs\n")
for r in erreurs:
    print(f"vrai={r['profil']}  juge={r['predit']}  (confiance {r['confiance']})  sujet={r['topic']}")
    print(f"  « {r['message']} »\n")