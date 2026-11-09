"""Étape 1 : générer le jeu de messages à évaluer.

Pour chaque profil × chaque sujet neutre, on génère N premiers messages.
Les sujets sont les MÊMES pour tous les profils : le juge ne peut donc
reconnaître le profil que grâce au ton, pas grâce au sujet.

Lancer depuis la racine du back (client_agent/) :
    python -m eval.generate --model qwen2.5:3b --n 4
"""
import argparse
import json
import random
import time
from pathlib import Path

from app.client_generator import generate_client
from app.llm_service import generate_response
from app.profiles import PROFILES, SUJETS_PAR_DEFAUT as TOPICS_NEUTRES
from app.prompt_builder import build_client_prompt


URGENCE_FIXE = "moyenne"


def nettoyer(texte: str) -> str:
    """Enlève les guillemets et le préfixe « Client : » que le modèle ajoute parfois."""
    t = texte.strip().strip('"«» \n')
    for prefixe in ("Client :", "Client:", "Client –", "Client -"):
        if t.startswith(prefixe):
            t = t[len(prefixe):].strip()
    return t.strip('"«» \n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None, help="modèle Ollama (défaut : OLLAMA_MODEL du .env)")
    parser.add_argument("--n", type=int, default=4, help="messages par profil et par sujet")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    random.seed(args.seed)
    model_tag = (args.model or "default").replace(":", "-").replace("/", "-")
    out = Path(args.out or f"eval/results/{model_tag}/generations.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)

    total = len(PROFILES) * len(TOPICS_NEUTRES) * args.n
    print(f"Génération de {total} messages avec {args.model or 'le modèle par défaut'} -> {out}")

    with out.open("w", encoding="utf-8") as f:
        i = 0
        for profil in PROFILES:
            for topic in TOPICS_NEUTRES:
                for _ in range(args.n):
                    i += 1
                    client = generate_client(i)
                    client.profil = profil
                    prompt = build_client_prompt(client, topic, URGENCE_FIXE)

                    t0 = time.time()
                    brut = generate_response(prompt, model=args.model)
                    latence = int((time.time() - t0) * 1000)

                    f.write(json.dumps({
                        "id": i,
                        "model": args.model or "default",
                        "profil": profil,
                        "topic": topic,
                        "urgency": URGENCE_FIXE,
                        "message": nettoyer(brut),
                        "latencyMs": latence,
                    }, ensure_ascii=False) + "\n")
                    print(f"[{i}/{total}] {profil:<10} {nettoyer(brut)[:70]}")

    print(f"\nTerminé : {out}")


if __name__ == "__main__":
    main()