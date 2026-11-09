"""Enregistrement des conversations simulées + évaluations qualité + décisions workforce dans PostgreSQL.

.env :  DATABASE_URL=postgresql://utilisateur:motdepasse@localhost:5432/callverse
Les tables sont créées automatiquement au démarrage du serveur.

Power BI / Dashboard BI :
  - v_powerbi_turns     : 1 ligne par message (conversations + tours)
  - v_bi_full           : vue complète (conversations + qualité + workforce)
  - v_daily_kpis        : KPIs agrégés par jour
  - v_profile_perf      : performance moyenne par profil client
  - v_topic_analysis    : analyse par thématique
  - v_escalation_log    : conversations escaladées avec raisons
  - v_criteria_scores   : scores détaillés par critère qualité
"""
import os

import psycopg2
from psycopg2.extras import execute_values

SCHEMA = """
-- ============================================================
-- TABLES CONVERSATIONS (simulation client <-> conseiller RAG)
-- ============================================================
CREATE TABLE IF NOT EXISTS sim_clients (
    id         BIGSERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    age        INT,
    city       TEXT,
    profile    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, age, city, profile)
);

CREATE TABLE IF NOT EXISTS sim_conversations (
    id                 TEXT PRIMARY KEY,
    client_id          BIGINT REFERENCES sim_clients(id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    profile            TEXT NOT NULL,
    topic              TEXT,
    urgency            TEXT,
    rag                BOOLEAN,
    requested_messages INT,
    completed_turns    INT,
    client_name        TEXT,
    client_age         INT,
    client_city        TEXT,
    client_model       TEXT,
    advisor_model      TEXT,
    total_latency_ms   INT,
    any_urgent         BOOLEAN
);

CREATE TABLE IF NOT EXISTS sim_turns (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES sim_conversations(id) ON DELETE CASCADE,
    turn            INT  NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('client', 'advisor')),
    content         TEXT NOT NULL,
    word_count      INT,
    latency_ms      INT,
    model           TEXT,
    intent          TEXT,
    urgent          BOOLEAN,
    modules         TEXT,
    specialists     TEXT,
    n_sources       INT,
    n_steps         INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (conversation_id, turn, role)
);

CREATE TABLE IF NOT EXISTS sim_sources (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES sim_conversations(id) ON DELETE CASCADE,
    turn            INT  NOT NULL,
    source_id       TEXT,
    title           TEXT,
    module          TEXT,
    score           REAL
);

-- ============================================================
-- TABLE EVALUATIONS QUALITÉ (Agent 3 — Quality Analyst)
-- ============================================================
CREATE TABLE IF NOT EXISTS quality_evaluations (
    id                   BIGSERIAL PRIMARY KEY,
    conversation_id      TEXT REFERENCES sim_conversations(id) ON DELETE CASCADE,
    evaluated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Score global
    global_score         INT,
    -- Scores par critère (0-100 chacun)
    score_pertinence     INT,
    score_exactitude     INT,
    score_groundedness   INT,
    score_empathie       INT,
    score_clarte         INT,
    score_conformite     INT,
    -- Classification
    priority             TEXT,          -- faible / moyen / eleve / critique
    requires_human_review BOOLEAN,
    compliance_check     TEXT,
    -- Résumé textuel
    strengths            TEXT,          -- liste concaténée
    improvements         TEXT,
    recommendations      TEXT,
    alerts               TEXT,
    -- Métadonnées
    mode                 TEXT,          -- gemini-llm, mock...
    lora_risk_label      TEXT,          -- OK / CRITIQUE / null
    lora_risk_status     TEXT,          -- ok / disabled / manual_only
    rag_reference_used   BOOLEAN,
    accuracy_status      TEXT,
    profile              TEXT,
    -- JSON complet pour flexibilité
    raw_json             JSONB
);

CREATE INDEX IF NOT EXISTS idx_quality_conversation ON quality_evaluations(conversation_id);
CREATE INDEX IF NOT EXISTS idx_quality_evaluated_at ON quality_evaluations(evaluated_at);
CREATE INDEX IF NOT EXISTS idx_quality_score ON quality_evaluations(global_score);
CREATE INDEX IF NOT EXISTS idx_quality_priority ON quality_evaluations(priority);

-- ============================================================
-- TABLE DÉCISIONS WORKFORCE MANAGER (Agent 4)
-- ============================================================
CREATE TABLE IF NOT EXISTS workforce_decisions (
    id                      BIGSERIAL PRIMARY KEY,
    conversation_id         TEXT REFERENCES sim_conversations(id) ON DELETE CASCADE,
    decided_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    audit_score             INT,
    status                  TEXT,   -- OPTIMAL / INTERVENTION_REQUISE
    -- Problèmes détectés (liste concaténée)
    problems                TEXT,
    -- Actions déclenchées
    nb_actions              INT,
    action_types            TEXT,   -- ex: "escalade_humain, formation"
    has_escalation          BOOLEAN,
    has_rag_relaunch        BOOLEAN,
    has_kb_signal           BOOLEAN,
    has_training            BOOLEAN,
    -- Résumé opérationnel
    staffing_impact         TEXT,
    training_module         TEXT,
    kb_update_required      BOOLEAN,
    -- JSON complet
    raw_json                JSONB
);

CREATE INDEX IF NOT EXISTS idx_workforce_conversation ON workforce_decisions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_workforce_decided_at ON workforce_decisions(decided_at);
CREATE INDEX IF NOT EXISTS idx_workforce_status ON workforce_decisions(status);

-- ============================================================
-- INDEXES ET COLONNES SUPPLÉMENTAIRES
-- ============================================================
ALTER TABLE sim_conversations ADD COLUMN IF NOT EXISTS client_id BIGINT REFERENCES sim_clients(id);
CREATE INDEX IF NOT EXISTS idx_sim_conversations_client ON sim_conversations(client_id);
CREATE INDEX IF NOT EXISTS idx_sim_conversations_profile ON sim_conversations(profile);
CREATE INDEX IF NOT EXISTS idx_sim_conversations_topic ON sim_conversations(topic);
CREATE INDEX IF NOT EXISTS idx_sim_conversations_created_at ON sim_conversations(created_at);
CREATE INDEX IF NOT EXISTS idx_sim_sources_conversation ON sim_sources(conversation_id, turn);

-- ============================================================
-- VUE POWER BI (compatibilité existante)
-- ============================================================
CREATE OR REPLACE VIEW v_powerbi_turns AS
SELECT c.id AS conversation_id, c.created_at, c.profile, c.topic, c.urgency, c.rag,
       c.client_name, c.client_age, c.client_city, c.client_model, c.advisor_model,
       t.turn, t.role, t.content, t.word_count, t.latency_ms, t.intent, t.urgent,
       t.modules, t.specialists, t.n_sources, t.n_steps
FROM sim_conversations c
JOIN sim_turns t ON t.conversation_id = c.id;

-- ============================================================
-- VUE ANALYTIQUE COMPLÈTE (BI Dashboard — jointure 360°)
-- ============================================================
CREATE OR REPLACE VIEW v_bi_full AS
SELECT
    c.id                  AS conversation_id,
    c.created_at,
    DATE(c.created_at)    AS conversation_date,
    c.profile,
    c.topic,
    c.urgency,
    c.rag,
    c.completed_turns,
    c.client_name,
    c.client_age,
    c.client_city,
    c.client_model,
    c.advisor_model,
    c.total_latency_ms,
    c.any_urgent,
    -- Scores qualité
    q.global_score,
    q.score_pertinence,
    q.score_exactitude,
    q.score_groundedness,
    q.score_empathie,
    q.score_clarte,
    q.score_conformite,
    q.priority            AS quality_priority,
    q.requires_human_review,
    q.alerts              AS quality_alerts,
    q.lora_risk_label,
    q.rag_reference_used,
    q.profile             AS quality_profile,
    -- Décisions workforce
    w.status              AS workforce_status,
    w.audit_score,
    w.nb_actions,
    w.action_types,
    w.has_escalation,
    w.has_rag_relaunch,
    w.has_kb_signal,
    w.has_training,
    w.staffing_impact,
    w.training_module,
    w.kb_update_required
FROM sim_conversations c
LEFT JOIN quality_evaluations q ON q.conversation_id = c.id
LEFT JOIN workforce_decisions w ON w.conversation_id = c.id;

-- ============================================================
-- VUE KPIs JOURNALIERS
-- ============================================================
CREATE OR REPLACE VIEW v_daily_kpis AS
SELECT
    DATE(c.created_at)                                     AS day,
    COUNT(DISTINCT c.id)                                   AS nb_conversations,
    ROUND(AVG(q.global_score)::NUMERIC, 1)                 AS avg_quality_score,
    ROUND(AVG(q.score_empathie)::NUMERIC, 1)               AS avg_empathie,
    ROUND(AVG(q.score_pertinence)::NUMERIC, 1)             AS avg_pertinence,
    ROUND(AVG(q.score_clarte)::NUMERIC, 1)                 AS avg_clarte,
    ROUND(AVG(q.score_conformite)::NUMERIC, 1)             AS avg_conformite,
    ROUND(AVG(c.total_latency_ms)::NUMERIC, 0)             AS avg_latency_ms,
    COUNT(CASE WHEN w.has_escalation THEN 1 END)           AS nb_escalations,
    ROUND(
        100.0 * COUNT(CASE WHEN w.has_escalation THEN 1 END)
        / NULLIF(COUNT(DISTINCT c.id), 0), 1
    )                                                      AS escalation_rate_pct,
    COUNT(CASE WHEN q.priority = 'critique' THEN 1 END)    AS nb_critical_alerts,
    ROUND(
        100.0 * COUNT(CASE WHEN w.status = 'OPTIMAL' THEN 1 END)
        / NULLIF(COUNT(DISTINCT c.id), 0), 1
    )                                                      AS resolution_rate_pct
FROM sim_conversations c
LEFT JOIN quality_evaluations q ON q.conversation_id = c.id
LEFT JOIN workforce_decisions w ON w.conversation_id = c.id
GROUP BY DATE(c.created_at)
ORDER BY day DESC;

-- ============================================================
-- VUE PERFORMANCE PAR PROFIL CLIENT
-- ============================================================
CREATE OR REPLACE VIEW v_profile_perf AS
SELECT
    c.profile,
    COUNT(DISTINCT c.id)                                   AS nb_conversations,
    ROUND(AVG(q.global_score)::NUMERIC, 1)                 AS avg_quality_score,
    ROUND(AVG(q.score_empathie)::NUMERIC, 1)               AS avg_empathie,
    ROUND(AVG(q.score_pertinence)::NUMERIC, 1)             AS avg_pertinence,
    ROUND(AVG(q.score_conformite)::NUMERIC, 1)             AS avg_conformite,
    ROUND(
        100.0 * COUNT(CASE WHEN w.has_escalation THEN 1 END)
        / NULLIF(COUNT(DISTINCT c.id), 0), 1
    )                                                      AS escalation_rate_pct,
    ROUND(
        100.0 * COUNT(CASE WHEN q.priority = 'critique' THEN 1 END)
        / NULLIF(COUNT(DISTINCT c.id), 0), 1
    )                                                      AS critical_alert_rate_pct,
    MIN(q.global_score)                                    AS min_score,
    MAX(q.global_score)                                    AS max_score
FROM sim_conversations c
LEFT JOIN quality_evaluations q ON q.conversation_id = c.id
LEFT JOIN workforce_decisions w ON w.conversation_id = c.id
GROUP BY c.profile
ORDER BY avg_quality_score DESC NULLS LAST;

-- ============================================================
-- VUE ANALYSE PAR THÉMATIQUE
-- ============================================================
CREATE OR REPLACE VIEW v_topic_analysis AS
SELECT
    COALESCE(c.topic, 'auto')                              AS topic,
    COUNT(DISTINCT c.id)                                   AS nb_conversations,
    ROUND(AVG(q.global_score)::NUMERIC, 1)                 AS avg_quality_score,
    ROUND(AVG(q.score_pertinence)::NUMERIC, 1)             AS avg_pertinence,
    ROUND(
        100.0 * COUNT(CASE WHEN w.has_escalation THEN 1 END)
        / NULLIF(COUNT(DISTINCT c.id), 0), 1
    )                                                      AS escalation_rate_pct,
    COUNT(CASE WHEN q.priority IN ('eleve', 'critique') THEN 1 END) AS nb_high_risk
FROM sim_conversations c
LEFT JOIN quality_evaluations q ON q.conversation_id = c.id
LEFT JOIN workforce_decisions w ON w.conversation_id = c.id
GROUP BY COALESCE(c.topic, 'auto')
ORDER BY nb_conversations DESC;

-- ============================================================
-- VUE JOURNAL DES ESCALADES
-- ============================================================
CREATE OR REPLACE VIEW v_escalation_log AS
SELECT
    c.id                  AS conversation_id,
    c.created_at,
    c.profile,
    c.topic,
    c.urgency,
    c.client_name,
    c.client_age,
    c.client_city,
    q.global_score,
    q.priority,
    q.alerts,
    q.requires_human_review,
    w.problems,
    w.action_types,
    w.staffing_impact
FROM sim_conversations c
JOIN quality_evaluations q ON q.conversation_id = c.id
JOIN workforce_decisions w ON w.conversation_id = c.id
WHERE w.has_escalation = TRUE OR q.priority IN ('eleve', 'critique')
ORDER BY c.created_at DESC;

-- ============================================================
-- VUE SCORES DÉTAILLÉS PAR CRITÈRE (pour graphiques spider/radar)
-- ============================================================
CREATE OR REPLACE VIEW v_criteria_scores AS
SELECT
    q.conversation_id,
    c.created_at,
    c.profile,
    c.topic,
    q.global_score,
    'pertinence'    AS criterion, q.score_pertinence    AS score FROM quality_evaluations q JOIN sim_conversations c ON c.id = q.conversation_id
UNION ALL
SELECT q.conversation_id, c.created_at, c.profile, c.topic, q.global_score,
    'empathie'      AS criterion, q.score_empathie      AS score FROM quality_evaluations q JOIN sim_conversations c ON c.id = q.conversation_id
UNION ALL
SELECT q.conversation_id, c.created_at, c.profile, c.topic, q.global_score,
    'clarte'        AS criterion, q.score_clarte        AS score FROM quality_evaluations q JOIN sim_conversations c ON c.id = q.conversation_id
UNION ALL
SELECT q.conversation_id, c.created_at, c.profile, c.topic, q.global_score,
    'conformite'    AS criterion, q.score_conformite    AS score FROM quality_evaluations q JOIN sim_conversations c ON c.id = q.conversation_id
UNION ALL
SELECT q.conversation_id, c.created_at, c.profile, c.topic, q.global_score,
    'groundedness'  AS criterion, q.score_groundedness  AS score FROM quality_evaluations q JOIN sim_conversations c ON c.id = q.conversation_id;
"""


def is_configured() -> bool:
    return bool(os.getenv("DATABASE_URL"))


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def init_db() -> bool:
    """Crée les tables et la vue si besoin. Renvoie False si DATABASE_URL n'est pas renseignée."""
    if not is_configured():
        print("  [db] DATABASE_URL absente : les conversations ne seront pas enregistrées.")
        return False
    conn = _connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(SCHEMA)
    finally:
        conn.close()
    return True


def _words(text: str) -> int:
    return len((text or "").split())


def save_conversation(conv: dict) -> bool:
    """Enregistre une conversation (résultat de simulation.run_conversation). Renvoie False si la base n'est pas configurée."""
    if not is_configured():
        return False

    turns = conv["turns"]
    rows, sources = [], []
    for t in turns:
        adv = t["advisor"]
        rows.append((conv["id"], t["turn"], "client", t["clientMessage"], _words(t["clientMessage"]),
                     t.get("clientLatencyMs"), conv.get("clientModel"), None, None, None, None, None, None))
        rows.append((conv["id"], t["turn"], "advisor", adv["answer"], _words(adv["answer"]),
                     adv.get("latencyMs"), adv.get("model"), adv.get("intent"), bool(adv.get("urgent")),
                     ", ".join(adv.get("modules") or []), ", ".join(adv.get("specialists") or []),
                     len(adv.get("sources") or []), len(adv.get("steps") or [])))
        for s in adv.get("sources") or []:
            sources.append((conv["id"], t["turn"], s.get("id"), s.get("title"), s.get("module"), s.get("score")))

    client = conv.get("client") or {}
    conn = _connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO sim_clients (name, age, city, profile) VALUES (%s,%s,%s,%s)
                   ON CONFLICT (name, age, city, profile) DO UPDATE SET name = EXCLUDED.name
                   RETURNING id""",
                (client.get("name") or "Inconnu", client.get("age"), client.get("city"), conv["profile"]),
            )
            client_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO sim_conversations
                   (id, client_id, created_at, profile, topic, urgency, rag, requested_messages, completed_turns,
                    client_name, client_age, client_city, client_model, advisor_model, total_latency_ms, any_urgent)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""",
                (conv["id"], client_id, conv["createdAt"], conv["profile"], conv.get("topic"), conv.get("urgency"),
                 conv.get("rag"), conv.get("messageCount"), len(turns), client.get("name"), client.get("age"),
                 client.get("city"), conv.get("clientModel"), conv.get("advisorModel"), conv.get("latencyMs"),
                 any(bool(t["advisor"].get("urgent")) for t in turns)),
            )
            execute_values(
                cur,
                """INSERT INTO sim_turns
                   (conversation_id, turn, role, content, word_count, latency_ms, model, intent, urgent,
                    modules, specialists, n_sources, n_steps)
                   VALUES %s ON CONFLICT (conversation_id, turn, role) DO NOTHING""",
                rows,
            )
            if sources:
                execute_values(
                    cur,
                    "INSERT INTO sim_sources (conversation_id, turn, source_id, title, module, score) VALUES %s",
                    sources,
                )
    finally:
        conn.close()
    return True


def save_quality_evaluation(conversation_id: str, evaluation: dict) -> bool:
    """Enregistre l'évaluation de l'Analyste Qualité dans PostgreSQL.
    evaluation = result['evaluation'] renvoyé par simulation.build_result
    """
    if not is_configured():
        return False

    import json as _json
    criteria = evaluation.get("criteria") or {}
    lora = evaluation.get("loraRisk") or {}
    rag_ref = evaluation.get("ragReference") or {}

    def _join(lst) -> str:
        return " | ".join(lst) if isinstance(lst, list) else (lst or "")

    conn = _connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO quality_evaluations
                   (conversation_id, global_score,
                    score_pertinence, score_exactitude, score_groundedness,
                    score_empathie, score_clarte, score_conformite,
                    priority, requires_human_review, compliance_check,
                    strengths, improvements, recommendations, alerts,
                    mode, lora_risk_label, lora_risk_status,
                    rag_reference_used, accuracy_status, profile, raw_json)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    conversation_id,
                    evaluation.get("globalScore"),
                    criteria.get("pertinence"),
                    criteria.get("exactitude"),
                    criteria.get("groundedness"),
                    criteria.get("empathie"),
                    criteria.get("clarte"),
                    criteria.get("conformite"),
                    evaluation.get("priority"),
                    bool(evaluation.get("requiresHumanReview")),
                    evaluation.get("complianceCheck"),
                    _join(evaluation.get("strengths")),
                    _join(evaluation.get("improvements")),
                    _join(evaluation.get("recommendations")),
                    _join(evaluation.get("alerts")),
                    evaluation.get("mode"),
                    lora.get("label"),
                    lora.get("status"),
                    bool(rag_ref.get("used")),
                    evaluation.get("accuracyStatus"),
                    evaluation.get("profile"),
                    _json.dumps(evaluation, ensure_ascii=False),
                ),
            )
    finally:
        conn.close()
    return True


def save_workforce_decision(conversation_id: str, decision: dict) -> bool:
    """Enregistre la décision du Workforce Manager dans PostgreSQL.
    decision = result['decision'] renvoyé par simulation.build_result
    """
    if not is_configured():
        return False

    import json as _json
    actions = decision.get("actions") or []
    action_types = ", ".join({a.get("type", "") for a in actions if a.get("type")})
    wf = decision.get("workforceSummary") or {}

    def _join(lst) -> str:
        return " | ".join(lst) if isinstance(lst, list) else (lst or "")

    conn = _connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO workforce_decisions
                   (conversation_id, audit_score, status,
                    problems, nb_actions, action_types,
                    has_escalation, has_rag_relaunch, has_kb_signal, has_training,
                    staffing_impact, training_module, kb_update_required, raw_json)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    conversation_id,
                    decision.get("auditScore"),
                    decision.get("status"),
                    _join(decision.get("problems")),
                    len(actions),
                    action_types,
                    any(a.get("type") == "escalade_humain" for a in actions),
                    any(a.get("type") == "relancer_rag" for a in actions),
                    any(a.get("type") == "signaler_kb" for a in actions),
                    any(a.get("type") == "formation" for a in actions),
                    wf.get("staffingImpact"),
                    wf.get("trainingModuleSuggested"),
                    bool(wf.get("kbUpdateRequired")),
                    _json.dumps(decision, ensure_ascii=False),
                ),
            )
    finally:
        conn.close()
    return True
