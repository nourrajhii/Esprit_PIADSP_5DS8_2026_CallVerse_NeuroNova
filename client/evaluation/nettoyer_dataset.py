"""Ré-applique les filtres de build_dataset sur un dataset déjà généré
et supprime les exemples qui ne passent plus.

python -m evaluation.nettoyer_dataset --data eval/dataset/train.jsonl
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from evaluation.build_dataset import MAX_FORMULE_EXIGEANT, formule_exigeant, raison_rejet

parser = argparse.ArgumentParser()
parser.add_argument("--data", default="eval/dataset/train.jsonl")
args = parser.parse_args()

path = Path(args.data)
lignes = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
gardes, rejets = [], Counter()
nb_formule = 0
for l in lignes:
    ex = json.loads(l)
    msg, profil = ex["messages"][-1]["content"], ex["profil"]
    raison = raison_rejet(msg, profil)
    if raison is None and profil == "exigeant" and formule_exigeant(msg):
        if nb_formule >= MAX_FORMULE_EXIGEANT:
            raison = "formule_repetee"
        else:
            nb_formule += 1
    if raison:
        rejets[raison] += 1
        print(f"SUPPRIMÉ ({raison}) [{profil}] {msg[:90]}")
    else:
        gardes.append(l)

path.with_suffix(".avant_nettoyage.jsonl").write_text("\n".join(lignes) + "\n", encoding="utf-8")  # sauvegarde
path.write_text("\n".join(gardes) + "\n", encoding="utf-8")

print(f"\n{len(lignes)} -> {len(gardes)} exemples  |  supprimés : {dict(rejets)}")
print("Par profil :", dict(Counter(json.loads(l)["profil"] for l in gardes)))