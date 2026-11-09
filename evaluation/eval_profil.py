"""Métrique 1 : fidélité au profil.

Un juge LLM lit chaque message SANS connaître le profil et doit deviner
lequel des 7 profils il exprime. On compare sa réponse au vrai profil.

Lancer depuis la racine du back (client_agent/) :
    python -m eval.eval_profil --gen eval/results/qwen2.5-3b/generations.jsonl --judge qwen2.5:7b
"""
import argparse
import json
import random
from collections import Counter
from pathlib import Path

from app.llm_service import generate_response
from app.profiles import PROFILES

PROFILS = list(PROFILES.keys())


def prompt_juge(message: str, ordre: list[str]) -> str:
    liste = "\n".join(
        f"- {p} : {PROFILES[p]['description']} Traits : {', '.join(PROFILES[p]['traits'])}."
        for p in ordre
    )
    return f"""Tu es un évaluateur expert en relation client.
Voici le premier message d'un client qui appelle un centre d'appel médical :

\"\"\"{message}\"\"\"

Quel profil de client ce message exprime-t-il le mieux ? Choisis UN SEUL profil parmi :
{liste}

Distinctions importantes :
- mecontent = reproche au service (promesse non tenue, rappel jamais fait, mauvaise expérience passée).
  impatient = pressé par le TEMPS, veut aller vite, sans forcément reprocher quelque chose au service.
- exigeant = réclame des garanties, une confirmation écrite, un nom précis, même poliment.
  calme = demande simple et posée, sans conditions particulières.
- nerveux = inquiet, a peur, cherche à être rassuré. confus = ne comprend pas, hésite, mélange les informations.

Base-toi uniquement sur le ton et la manière de parler, pas sur le sujet de l'appel.

Réponds UNIQUEMENT en JSON, sans texte autour :
{{"profil": "<un des profils ci-dessus>", "confiance": <ta certitude sur TA réponse, de 1 = je devine à 5 = certain>}}"""

def parser_reponse(texte: str) -> tuple[str, int]:
    """Lit la réponse JSON du juge. Renvoie ('invalide', 0) si illisible."""
    try:
        debut, fin = texte.index("{"), texte.rindex("}") + 1
        data = json.loads(texte[debut:fin])
        profil = str(data.get("profil", "")).strip().lower()
        profil = profil.replace("é", "e").replace("è", "e").replace("ê", "e")
        conf = int(data.get("confiance", 0))
        return (profil if profil in PROFILS else "invalide"), conf
    except (ValueError, json.JSONDecodeError, TypeError):
        return "invalide", 0


def juger(lignes: list[dict], judge: str, seed: int) -> list[dict]:
    rng = random.Random(seed)
    resultats = []
    for k, g in enumerate(lignes, 1):
        ordre = PROFILS[:]
        rng.shuffle(ordre)  # ordre aléatoire pour éviter que le juge favorise le 1er profil
        brut = generate_response(prompt_juge(g["message"], ordre), model=judge, temperature=0.0)
        predit, conf = parser_reponse(brut)
        resultats.append({**g, "predit": predit, "confiance": conf, "juge": judge})
        ok = "OK " if predit == g["profil"] else "XX "
        print(f"[{k}/{len(lignes)}] {ok} vrai={g['profil']:<10} prédit={predit:<10} conf={conf}")
    return resultats


def calculer(resultats: list[dict]) -> dict:
    n = len(resultats)
    labels = PROFILS + ["invalide"]
    matrice = {v: Counter() for v in PROFILS}
    for r in resultats:
        matrice[r["profil"]][r["predit"]] += 1

    par_profil = {}
    for p in PROFILS:
        vp = matrice[p][p]
        total_vrai = sum(matrice[p].values())
        total_predit = sum(matrice[v][p] for v in PROFILS)
        rappel = vp / total_vrai if total_vrai else 0.0
        precision = vp / total_predit if total_predit else 0.0
        f1 = 2 * precision * rappel / (precision + rappel) if precision + rappel else 0.0
        confondu = Counter({k: c for k, c in matrice[p].items() if k != p}).most_common(1)
        par_profil[p] = {
            "n": total_vrai,
            "rappel": round(rappel, 3),
            "precision": round(precision, 3),
            "f1": round(f1, 3),
            "souvent_confondu_avec": confondu[0][0] if confondu else None,
        }

    correct = sum(r["predit"] == r["profil"] for r in resultats)
    return {
        "n_messages": n,
        "accuracy": round(correct / n, 3),
        "macro_f1": round(sum(v["f1"] for v in par_profil.values()) / len(PROFILS), 3),
        "hasard": round(1 / len(PROFILS), 3),
        "taux_invalide": round(sum(r["predit"] == "invalide" for r in resultats) / n, 3),
        "confiance_moyenne": round(sum(r["confiance"] for r in resultats) / n, 2),
        "par_profil": par_profil,
        "matrice_confusion": {
            "lignes=vrai, colonnes=prédit": labels,
            **{p: [matrice[p][l] for l in labels] for p in PROFILS},
        },
    }


def afficher(rapport: dict) -> None:
    print("\n" + "=" * 60)
    print("FIDÉLITÉ AU PROFIL")
    print("=" * 60)
    print(f"Messages évalués : {rapport['n_messages']}")
    print(f"Accuracy         : {rapport['accuracy']:.1%}   (hasard = {rapport['hasard']:.1%})")
    print(f"Macro-F1         : {rapport['macro_f1']:.3f}")
    print(f"Réponses juge invalides : {rapport['taux_invalide']:.1%}")
    print(f"\n{'profil':<11}{'rappel':>8}{'précision':>11}{'F1':>7}   confondu avec")
    for p, v in rapport["par_profil"].items():
        print(f"{p:<11}{v['rappel']:>8.0%}{v['precision']:>11.0%}{v['f1']:>7.2f}   {v['souvent_confondu_avec'] or '-'}")

    labels = rapport["matrice_confusion"]["lignes=vrai, colonnes=prédit"]
    print("\nMatrice de confusion (lignes = vrai profil, colonnes = profil prédit)")
    print(" " * 11 + "".join(f"{l[:5]:>6}" for l in labels))
    for p in PROFILS:
        print(f"{p:<11}" + "".join(f"{c:>6}" for c in rapport["matrice_confusion"][p]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gen", required=True, help="fichier generations.jsonl")
    parser.add_argument("--judge", default="qwen2.5:7b", help="modèle juge Ollama (plus gros que le modèle testé)")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    gen_path = Path(args.gen)
    lignes = [json.loads(l) for l in gen_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    resultats = juger(lignes, args.judge, args.seed)
    rapport = calculer(resultats)
    rapport["juge"] = args.judge
    afficher(rapport)

    dossier = gen_path.parent
    with (dossier / "profil_details.jsonl").open("w", encoding="utf-8") as f:
        for r in resultats:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (dossier / "profil_rapport.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRésultats enregistrés dans {dossier}/profil_rapport.json et profil_details.jsonl")


if __name__ == "__main__":
    main()