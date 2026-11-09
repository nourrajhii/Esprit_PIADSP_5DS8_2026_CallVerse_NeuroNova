"""migrate_sqlite_to_pg.py
==============================
Migre les évaluations qualité existantes de SQLite → PostgreSQL.

Usage (depuis le dossier RAG/) :
    python migrate_sqlite_to_pg.py

Prérequis :
    - DATABASE_URL configuré dans .env
    - Les tables PostgreSQL créées (uvicorn server:app au moins 1 fois)
    - La SQLite existe : backend/quality/quality_evaluations.sqlite3
"""
import json
import os
import sqlite3
from pathlib import Path

# Charger le .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

import psycopg2

SQLITE_PATH = Path(__file__).parent / "backend" / "quality" / "quality_evaluations.sqlite3"
DATABASE_URL = os.environ.get("DATABASE_URL", "")


def migrate():
    if not DATABASE_URL:
        print("❌ DATABASE_URL non définie dans .env")
        return

    if not SQLITE_PATH.exists():
        print(f"❌ SQLite introuvable : {SQLITE_PATH}")
        return

    # Lire toutes les évaluations depuis SQLite
    with sqlite3.connect(SQLITE_PATH) as sqlite_conn:
        rows = sqlite_conn.execute(
            "SELECT id, evaluated_at, global_score, report_json FROM evaluations ORDER BY evaluated_at"
        ).fetchall()

    print(f"📦 {len(rows)} évaluations trouvées dans SQLite")

    if not rows:
        print("ℹ️  Rien à migrer.")
        return

    # Connexion PostgreSQL
    pg_conn = psycopg2.connect(DATABASE_URL)
    inserted = 0
    skipped = 0
    errors = 0

    try:
        with pg_conn, pg_conn.cursor() as cur:
            for row_id, evaluated_at, global_score, report_json_str in rows:
                try:
                    report = json.loads(report_json_str)
                    criteria = report.get("criteria") or {}
                    lora = report.get("loraRisk") or {}
                    rag_ref = report.get("ragReference") or {}

                    def _join(lst):
                        return " | ".join(lst) if isinstance(lst, list) else (lst or "")

                    # L'id SQLite = conversationId de l'évaluation (ex: "abc123-t1")
                    # On tente de retrouver le conversation_id parent (sans le "-t1")
                    conv_id = row_id.split("-t")[0] if "-t" in row_id else row_id

                    # Vérifier si la conversation existe dans PostgreSQL
                    cur.execute("SELECT 1 FROM sim_conversations WHERE id = %s", (conv_id,))
                    conv_exists = cur.fetchone() is not None

                    if not conv_exists:
                        print(f"  ⚠️  Conversation {conv_id} absente de sim_conversations — évaluation insérée sans FK")
                        # On insère quand même mais sans foreign key (conv_id = None)
                        effective_conv_id = None
                    else:
                        effective_conv_id = conv_id

                    cur.execute(
                        """INSERT INTO quality_evaluations
                           (conversation_id, evaluated_at, global_score,
                            score_pertinence, score_exactitude, score_groundedness,
                            score_empathie, score_clarte, score_conformite,
                            priority, requires_human_review, compliance_check,
                            strengths, improvements, recommendations, alerts,
                            mode, lora_risk_label, lora_risk_status,
                            rag_reference_used, accuracy_status, profile, raw_json)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT DO NOTHING""",
                        (
                            effective_conv_id,
                            evaluated_at,
                            global_score,
                            criteria.get("pertinence"),
                            criteria.get("exactitude"),
                            criteria.get("groundedness"),
                            criteria.get("empathie"),
                            criteria.get("clarte"),
                            criteria.get("conformite"),
                            report.get("priority"),
                            bool(report.get("requiresHumanReview")),
                            report.get("complianceCheck"),
                            _join(report.get("strengths")),
                            _join(report.get("improvements")),
                            _join(report.get("recommendations")),
                            _join(report.get("alerts")),
                            report.get("mode"),
                            lora.get("label"),
                            lora.get("status"),
                            bool(rag_ref.get("used")),
                            report.get("accuracyStatus"),
                            report.get("profile"),
                            report_json_str,
                        ),
                    )
                    inserted += 1
                    print(f"  ✅ {row_id} (score: {global_score})")
                except Exception as e:
                    errors += 1
                    print(f"  ❌ Erreur sur {row_id}: {e}")

    finally:
        pg_conn.close()

    print(f"\n{'='*50}")
    print(f"✅ Migration terminée : {inserted} insérés | {skipped} ignorés | {errors} erreurs")
    print(f"{'='*50}")
    print("\n📊 Tu peux maintenant lancer le dashboard BI !")


if __name__ == "__main__":
    migrate()
