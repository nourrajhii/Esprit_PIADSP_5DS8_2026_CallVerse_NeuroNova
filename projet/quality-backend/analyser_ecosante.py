"""Audit des scores Quality Analyst e-commerce / santé.

Lit uniquement la SQLite locale, les annotations humaines et le CSV du benchmark.
Aucun appel réseau, aucune modification de la base ou des annotations.

Depuis quality-backend :
    .\\.venv\\Scripts\\python.exe .\\analyser_ecosante.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATASETS = ROOT / "datasets"
ANNOTATIONS = DATASETS / "annotations_ecommerce_sante_A.csv"
PREDICTIONS_CSV = DATASETS / "benchmark_predictions_ecommerce_sante.csv"
SQLITE = Path(os.getenv("QUALITY_DB_PATH", str(ROOT / "quality_evaluations.sqlite3")))
OUTPUT = DATASETS / "audit_ecosante.csv"
WEIGHTS = {"pertinence": .35, "empathie": .20, "clarte": .20, "conformite": .25}


def read_csv(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Fichier absent : {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def numeric(value, label):
    value = str(value if value is not None else "").strip().replace(",", ".")
    if not value:
        raise ValueError(f"{label}: note humaine manquante")
    n = float(value)
    if not math.isfinite(n) or not 0 <= n <= 100:
        raise ValueError(f"{label}: note invalide = {value}")
    return n


def human_total(row):
    return sum(numeric(row.get(f"{k}_humaine"), k) * weight for k, weight in WEIGHTS.items())


def fetch_reports(db_path: Path):
    if not db_path.exists():
        raise FileNotFoundError(f"Base SQLite introuvable : {db_path}")
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT id, report_json FROM evaluations").fetchall()
    result = {}
    for ident, payload in rows:
        data = json.loads(payload)
        if ident != data.get("conversationId"):
            print(f"AVERTISSEMENT : ID incoherent dans SQLite pour {ident}")
        result[ident] = data
    return result


def evaluate(annotations, csv_rows, reports):
    csv_by_id = {str(r.get("conversation_id", "")).strip(): r for r in csv_rows}
    output, pairs, human_flags, predicted_flags = [], [], [], []
    for ann in annotations:
        sid = str(ann.get("conversation_id", "")).strip()
        if not sid:
            raise ValueError("Ligne d'annotation sans conversation_id")
        human = human_total(ann)
        flag = str(ann.get("critique_humain", "")).strip().lower()
        if flag not in {"oui", "non"}:
            raise ValueError(f"{sid}: critique_humain doit etre oui ou non")
        csv_row = csv_by_id.get(sid, {})
        db_report = reports.get(sid)
        db_score = db_report.get("globalScore") if db_report else None
        csv_score = csv_row.get("score_ia", "")
        if csv_row.get("statut", "").upper() == "OK" and db_report is None:
            print(f"ATTENTION : {sid} = OK dans CSV mais absent de SQLite")
        if db_report is not None and csv_row.get("statut", "").upper() == "OK":
            if csv_score and abs(float(csv_score) - float(db_score)) > .01:
                print(f"ATTENTION : {sid} : score CSV {csv_score} != SQLite {db_score}")
        delta = float(db_score) - human if db_score is not None else None
        if delta is not None:
            pairs.append((sid, float(db_score), human, delta))
            human_flags.append(flag == "oui")
            predicted_flags.append(db_report.get("priority") == "critique")
        output.append({
            "conversation_id": sid,
            "score_humain": round(human, 2),
            "score_gemini": db_score if db_score is not None else "",
            "ecart_ia_moins_humain": round(delta, 2) if delta is not None else "",
            "erreur_absolue": round(abs(delta), 2) if delta is not None else "",
            "critique_humain": flag,
            "priorite_ia": db_report.get("priority", "") if db_report else "",
            "statut": "APPARIE" if delta is not None else "SANS_PREDICTION",
        })
    return output, pairs, human_flags, predicted_flags


def main():
    annotations = read_csv(ANNOTATIONS)
    old_results = read_csv(PREDICTIONS_CSV)
    reports = fetch_reports(SQLITE)
    if len(set(row.get("conversation_id", "") for row in annotations)) != len(annotations):
        raise ValueError("IDs d'annotations dupliques")
    output, pairs, truth, prediction = evaluate(annotations, old_results, reports)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(output[0]))
        writer.writeheader(); writer.writerows(output)
    print(f"Annotations : {len(annotations)} | Appariements SQLite : {len(pairs)}")
    print(f"Audit : {OUTPUT}")
    if not pairs:
        print("Aucun appariement. Verifie QUALITY_DB_PATH et les conversation_id.")
        return 1
    diffs = [p[3] for p in pairs]
    mae = sum(map(abs, diffs)) / len(diffs)
    rmse = math.sqrt(sum(x*x for x in diffs) / len(diffs))
    tp = sum(t and p for t, p in zip(truth, prediction))
    fp = sum(not t and p for t, p in zip(truth, prediction))
    fn = sum(t and not p for t, p in zip(truth, prediction))
    tn = sum(not t and not p for t, p in zip(truth, prediction))
    prec = tp / (tp+fp) if tp+fp else 0
    recall = tp / (tp+fn) if tp+fn else 0
    f1 = 2*prec*recall/(prec+recall) if prec+recall else 0
    print(f"MAE={mae:.2f} | RMSE={rmse:.2f} (points / 100)")
    print(f"Critiques : TP={tp}, FP={fp}, FN={fn}, TN={tn}; P={prec:.2f}, R={recall:.2f}, F1={f1:.2f}")
    print("Ecarts absolus les plus importants :")
    for sid, score, human, delta in sorted(pairs, key=lambda p: abs(p[3]), reverse=True)[:5]:
        print(f"  {sid}: IA={score:g}, humain={human:.2f}, ecart={delta:+.2f}")
    no_predictions = [r['conversation_id'] for r in output if r['statut'] == 'SANS_PREDICTION']
    if no_predictions:
        print("Scenarios sans evaluation IA : " + ", ".join(no_predictions))
    print("Limite : F1 sur peu de positifs ; noter le support et la non-representativite.")
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, FileNotFoundError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        sys.exit(1)
