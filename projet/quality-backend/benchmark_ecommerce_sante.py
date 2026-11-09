"""Benchmark exploratoire : pharmacie en ligne (ne touche pas aux fichiers telecom).
Usage : python benchmark_ecommerce_sante.py --dry-run
        python benchmark_ecommerce_sante.py
Nécessite FastAPI sur 127.0.0.1:8001 avec GEMINI_MODEL=gemini-3.6-flash.
"""
from __future__ import annotations
import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "datasets" / "scenarios_ecommerce_sante.json"
OUTPUT = ROOT / "datasets" / "benchmark_predictions_ecommerce_sante.csv"
BACKUP = ROOT / "datasets" / "benchmark_predictions_ecommerce_sante_backup.csv"
API = "http://127.0.0.1:8001"
MODEL = "gemini-3.6-flash"  # Comparaisons homogènes avec une même version de modèle.
FIELDS = ["conversation_id", "statut", "score_ia", "priorite_ia", "revue_humaine", "erreur"]


def read_scenarios():
    scenarios = json.loads(DATASET.read_text(encoding="utf-8-sig"))
    if not isinstance(scenarios, list) or len(scenarios) != 10:
        raise ValueError("Le dataset doit contenir 10 scenarios.")
    ids = []
    for s in scenarios:
        sid = s["scenario"]
        assert isinstance(sid, str) and sid.startswith("ECOSANTE-"), f"ID inattendu : {sid}"
        assert s["request"]["message"] and s["response"]["answer"]
        ids.append(sid)
    if len(set(ids)) != len(ids):
        raise ValueError("IDs dupliques.")
    return scenarios


def previous(scenarios):
    rows = {s["scenario"]: {k: "" for k in FIELDS} | {"conversation_id": s["scenario"]} for s in scenarios}
    if OUTPUT.exists():
        with OUTPUT.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not set(FIELDS).issubset(reader.fieldnames or []):
                raise ValueError("Colonnes CSV non conformes; aucun ecrasement effectue.")
            for r in reader:
                sid = r.get("conversation_id", "").strip()
                if sid not in rows:
                    raise ValueError(f"Ligne d'un autre dataset dans {OUTPUT.name} : {sid}")
                rows[sid] = {k: r.get(k, "") for k in FIELDS}
    return rows


def success(row):
    return row["statut"].upper() == "OK" and row["score_ia"] != ""


def call(path, payload=None, timeout=12):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
    req = Request(API + path, data=data, method="POST" if data else "GET",
                  headers={"Content-Type": "application/json; charset=utf-8"} if data else {})
    with urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def save(scenarios, rows):
    temp = OUTPUT.with_suffix(".tmp")
    try:
        with temp.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows[s["scenario"]] for s in scenarios)
            f.flush(); os.fsync(f.fileno())
        os.replace(temp, OUTPUT)
    finally:
        if temp.exists(): temp.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pause", type=int, default=25)
    args = parser.parse_args()
    if args.pause < 0 or args.pause > 300:
        parser.error("pause doit etre comprise entre 0 et 300 secondes")
    scenarios = read_scenarios()
    rows = previous(scenarios)
    remaining = [s for s in scenarios if not success(rows[s["scenario"]])]
    print(f"E-commerce/sante : {len(scenarios) - len(remaining)}/10 deja reussies; {len(remaining)} restantes.")
    for s in remaining: print(" -", s["scenario"])
    if args.dry_run or not remaining:
        print("Aucun appel au LLM.")
        return 0
    health = call("/health")
    if health.get("status") != "up" or health.get("llmConfigured") is not True:
        raise RuntimeError("FastAPI/cle Gemini non prets; aucun appel envoye.")
    if health.get("model") != MODEL:
        raise RuntimeError(f"Le serveur utilise {health.get('model')}; attendu {MODEL} pour une baseline homogene.")
    if OUTPUT.exists() and not BACKUP.exists():
        shutil.copy2(OUTPUT, BACKUP)
        print("Copie de securite creee :", BACKUP)
    consecutive_error = 0
    for i, s in enumerate(remaining, 1):
        if i > 1 and args.pause:
            print(f"Pause de {args.pause} secondes...")
            time.sleep(args.pause)
        sid = s["scenario"]
        print(f"[{i}/{len(remaining)}] {sid}", flush=True)
        body = {"conversationId": sid, "request": s["request"], "response": s["response"]}
        try:
            report = call("/evaluate", body, timeout=160)
            score = report.get("globalScore")
            if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 100 or report.get("conversationId") != sid:
                raise ValueError("Reponse invalide/score absent.")
            rows[sid] = {"conversation_id": sid, "statut": "OK", "score_ia": str(score), "priorite_ia": str(report.get("priority", "")), "revue_humaine": str(report.get("requiresHumanReview", "")), "erreur": ""}
            consecutive_error = 0
            print(f"  OK {score}/100, priorite={report.get('priority')}")
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as e:
            rows[sid] = {"conversation_id": sid, "statut": "ERREUR", "score_ia": "", "priorite_ia": "", "revue_humaine": "", "erreur": str(e)}
            consecutive_error += 1
            print(f"  ERREUR : {e}")
        save(scenarios, rows)
        if consecutive_error >= 2:
            print("2 erreurs consecutives : arret preventif. Relancer plus tard, sans perdre les scores.")
            break
    done = sum(success(rows[s["scenario"]]) for s in scenarios)
    print(f"Bilan : {done}/10 enregistres. CSV : {OUTPUT}")
    return 0 if done == 10 else 2

if __name__ == "__main__":
    try: sys.exit(main())
    except (RuntimeError, OSError, ValueError, KeyError, AssertionError) as e:
        print("ERREUR :", e, file=sys.stderr)
        sys.exit(1)
