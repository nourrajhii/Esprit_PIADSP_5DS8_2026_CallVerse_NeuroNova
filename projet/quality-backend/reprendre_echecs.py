r"""Reprendre uniquement les évaluations ayant échoué dans benchmark_predictions.csv.

À déposer à la racine de quality-backend. Sans dépendances supplémentaires.
Sauvegarde après chaque réponse pour ne pas perdre les scores existants.

Usage:
  .\.venv\Scripts\python.exe .\reprendre_echecs.py --dry-run
  .\.venv\Scripts\python.exe .\reprendre_echecs.py
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "datasets" / "scenarios_telecom.json"
CSV_PATH = ROOT / "datasets" / "benchmark_predictions.csv"
BACKUP = ROOT / "datasets" / "benchmark_predictions_backup_avant_reprise.csv"
API = "http://127.0.0.1:8001"
EXPECTED_MODEL = "gemini-3.6-flash"  # Baseline des 5 résultats obtenus
FIELDS = ["conversation_id", "statut", "score_ia", "priorite_ia", "revue_humaine", "erreur"]


def load_data():
    if not DATASET.is_file():
        raise RuntimeError(f"Dataset absent : {DATASET}")
    if not CSV_PATH.is_file():
        raise RuntimeError(f"CSV absent : {CSV_PATH}. Ne pas recommencer tout le benchmark automatiquement.")

    scenarios = json.loads(DATASET.read_text(encoding="utf-8-sig"))
    if not isinstance(scenarios, list) or len(scenarios) != 10:
        raise RuntimeError("Dataset attendu : exactement 10 scénarios.")
    ids = [s["scenario"] for s in scenarios]
    if len(set(ids)) != len(ids):
        raise RuntimeError("Identifiants de scénarios dupliqués.")

    with CSV_PATH.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not set(FIELDS).issubset(reader.fieldnames):
            raise RuntimeError(f"Colonnes CSV attendues : {', '.join(FIELDS)}")
        rows = list(reader)
    by_id = {}
    for r in rows:
        rid = r["conversation_id"].strip()
        if rid in by_id:
            raise RuntimeError(f"ID dupliqué dans le CSV : {rid}")
        by_id[rid] = {k: r.get(k, "") for k in FIELDS}
    if set(ids) != set(by_id):
        raise RuntimeError("Les 10 identifiants du CSV doivent correspondre exactement au dataset.")
    return scenarios, by_id


def successful(row):
    return row["statut"].strip().upper() == "OK" and row["score_ia"].strip() != ""


def api_json(path, payload=None, timeout=12):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = Request(
        API + path,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"} if data else {},
        method="POST" if data is not None else "GET",
    )
    with urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def save_csv(scenarios, by_id):
    tmp = CSV_PATH.with_name(CSV_PATH.name + ".tmp")
    # os.replace conserve le fichier source entier, même après interruption du script.
    try:
        with tmp.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            for scenario in scenarios:
                writer.writerow(by_id[scenario["scenario"]])
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, CSV_PATH)
    finally:
        if tmp.exists():
            tmp.unlink()


def run(pause, max_overloads, dry_run):
    scenarios, by_id = load_data()
    done = sum(successful(by_id[s["scenario"]]) for s in scenarios)
    pending = [s for s in scenarios if not successful(by_id[s["scenario"]])]
    print(f"Déjà réussies et conservées : {done}/10")
    print(f"Restantes : {len(pending)}")
    for s in pending:
        print(" -", s["scenario"])
    if dry_run or not pending:
        print("Aucun appel Gemini effectué." if dry_run else "Benchmark déjà complet.")
        return 0

    try:
        health = api_json("/health", timeout=10)
    except (HTTPError, URLError, TimeoutError, ValueError) as e:
        raise RuntimeError(f"FastAPI injoignable sur {API}. Démarrer uvicorn. Détail : {e}") from e
    if health.get("status") != "up" or health.get("llmConfigured") is not True:
        raise RuntimeError("FastAPI actif mais clé Gemini absente ou service non prêt.")
    if health.get("model") != EXPECTED_MODEL:
        raise RuntimeError(
            f"Modèle actuel : {health.get('model')!r}. Pour préserver un benchmark homogène, "
            f"redémarrer FastAPI avec GEMINI_MODEL={EXPECTED_MODEL}."
        )

    if not BACKUP.exists():
        shutil.copy2(CSV_PATH, BACKUP)
        print(f"Sauvegarde créée : {BACKUP.name}")
    print(f"Backend OK ; modèle : {health['model']} ; une requête par scénario manquant.")
    print("L'API Gemini peut consommer du quota ; arrêt après surcharge répétée.")

    last_call = False
    consecutive_overloads = 0
    for i, scenario in enumerate(pending, start=1):
        if last_call and pause:
            print(f"Pause de {pause} secondes entre les appels ...", flush=True)
            time.sleep(pause)
        last_call = True
        sid = scenario["scenario"]
        print(f"[{i}/{len(pending)}] {sid}", flush=True)
        payload = {
            "conversationId": sid,
            "request": scenario["request"],
            "response": scenario["response"],
        }
        try:
            response = api_json("/evaluate", payload, timeout=160)
            score = response.get("globalScore")
            if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 100:
                raise ValueError("Score manquant ou hors intervalle 0-100 dans la réponse JSON.")
            if response.get("conversationId") != sid:
                raise ValueError("L'identifiant retourné ne correspond pas au scénario.")
            by_id[sid] = {
                "conversation_id": sid,
                "statut": "OK",
                "score_ia": str(score),
                "priorite_ia": str(response.get("priority", "")),
                "revue_humaine": str(response.get("requiresHumanReview", "")),
                "erreur": "",
            }
            consecutive_overloads = 0
            print(f"  OK : {score}/100 ; priorité={response.get('priority')}", flush=True)
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            error_message = str(exc)
            code = exc.code if isinstance(exc, HTTPError) else None
            by_id[sid]["statut"] = "ERREUR"
            by_id[sid]["score_ia"] = ""
            by_id[sid]["priorite_ia"] = ""
            by_id[sid]["revue_humaine"] = ""
            by_id[sid]["erreur"] = error_message
            print(f"  ERREUR : {error_message}", flush=True)
            if code in (429, 503):
                consecutive_overloads += 1
            else:
                consecutive_overloads = 0
        save_csv(scenarios, by_id)
        if consecutive_overloads >= max_overloads:
            print(f"Arrêt de sécurité : {max_overloads} erreurs temporaires consécutives. Reprendre plus tard.")
            break

    done_after = sum(successful(by_id[s["scenario"]]) for s in scenarios)
    print(f"Bilan : {done_after}/10 analyses réussies et sauvegardées.")
    print(f"Fichier : {CSV_PATH}")
    return 0 if done_after == 10 else 2


def main():
    p = argparse.ArgumentParser(description="Reprendre les évaluations échouées sans modifier celles réussies.")
    p.add_argument("--dry-run", action="store_true", help="Afficher les cas restants sans requête réseau.")
    p.add_argument("--pause", type=int, default=25, help="Pause entre appels (secondes, défaut 25).")
    p.add_argument("--max-overloads", type=int, default=2, help="Arrêter après N erreurs 503/429 consécutives (défaut 2).")
    args = p.parse_args()
    if not (0 <= args.pause <= 600) or not (1 <= args.max_overloads <= 10):
        p.error("Paramètres hors limites.")
    try:
        return run(args.pause, args.max_overloads, args.dry_run)
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        print("ERREUR :", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
