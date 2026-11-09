"""
Dashboard BI — Centre d'Assistance Client PharmaShop
======================================================
Streamlit app connectée directement à PostgreSQL callverse.

Lancement :
    cd C:/Users/samar/Desktop/PI/dashboard
    streamlit run app.py
"""

import json
import os
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import streamlit as st
from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "RAG", ".env"))
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:nour@localhost:5432/callverse")

PROFILE_LABELS = {
    "calme": "😌 Calme", "impatient": "⚡ Impatient", "nerveux": "😰 Nerveux",
    "mecontent": "😠 Mécontent", "fidele": "⭐ Fidèle", "confus": "❓ Confus",
    "exigeant": "💼 Exigeant", "heureux": "😊 Heureux",
}
PROFILE_COLORS = {
    "calme": "#4CAF50", "impatient": "#FF9800", "nerveux": "#9C27B0",
    "mecontent": "#F44336", "fidele": "#2196F3", "confus": "#795548",
    "exigeant": "#607D8B", "heureux": "#FFEB3B",
}

# ── Connexion DB ───────────────────────────────────────────────────────────────
@st.cache_resource
def get_conn():
    return psycopg2.connect(DATABASE_URL)


def query(sql: str, params=None) -> pd.DataFrame:
    try:
        conn = get_conn()
        return pd.read_sql_query(sql, conn, params=params)
    except Exception as e:
        st.error(f"❌ DB error: {e}")
        return pd.DataFrame()


# ── Layout ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PharmaShop BI Dashboard",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .metric-card { background: #1e1e2e; border-radius: 12px; padding: 20px; text-align: center; }
    .metric-value { font-size: 2.5rem; font-weight: 700; color: #cba6f7; }
    .metric-label { font-size: 0.85rem; color: #a6adc8; margin-top: 4px; }
    .stMetric label { color: #cdd6f4 !important; }
    [data-testid="stSidebar"] { background-color: #181825; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/pharmacy-shop.png", width=60)
    st.title("PharmaShop BI")
    st.caption("Digital Twin — Centre d'assistance client")
    st.divider()

    page = st.radio("Navigation", [
        "📊 Vue globale",
        "📈 Tendances temporelles",
        "🎭 Analyse par profil",
        "🔬 Critères qualité",
        "⚠️ Alertes & Escalades",
        "📋 Conversations récentes",
    ])

    st.divider()
    if st.button("🔄 Rafraîchir les données"):
        st.cache_data.clear()
        st.rerun()

    st.caption(f"Mise à jour : {datetime.now().strftime('%H:%M:%S')}")


# ════════════════════════════════════════════════════════════════════════════════
# PAGE 1 — VUE GLOBALE
# ════════════════════════════════════════════════════════════════════════════════
if page == "📊 Vue globale":
    st.title("📊 Vue globale — KPIs du centre d'assistance")

    df_kpi = query("""
        SELECT
            COUNT(DISTINCT c.id)                              AS nb_conversations,
            ROUND(AVG(q.global_score)::NUMERIC, 1)            AS score_moyen,
            ROUND(100.0 * COUNT(CASE WHEN w.status = 'OPTIMAL' THEN 1 END)
                / NULLIF(COUNT(DISTINCT c.id), 0), 1)         AS taux_resolution,
            ROUND(100.0 * COUNT(CASE WHEN w.has_escalation THEN 1 END)
                / NULLIF(COUNT(DISTINCT c.id), 0), 1)         AS taux_escalade,
            COUNT(CASE WHEN q.priority = 'critique' THEN 1 END) AS alertes_critiques,
            ROUND(AVG(c.total_latency_ms)::NUMERIC, 0)        AS latence_moy_ms
        FROM sim_conversations c
        LEFT JOIN quality_evaluations q ON q.conversation_id = c.id
        LEFT JOIN workforce_decisions w ON w.conversation_id = c.id
    """)

    if not df_kpi.empty and df_kpi.iloc[0]["nb_conversations"] > 0:
        row = df_kpi.iloc[0]
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("💬 Conversations", int(row["nb_conversations"]))
        c2.metric("⭐ Score qualité", f"{row['score_moyen']}/100" if row["score_moyen"] else "—")
        c3.metric("✅ Taux résolution", f"{row['taux_resolution']}%" if row["taux_resolution"] else "—")
        c4.metric("🚨 Taux escalade", f"{row['taux_escalade']}%" if row["taux_escalade"] else "—")
        c5.metric("🔴 Alertes critiques", int(row["alertes_critiques"] or 0))
        c6.metric("⏱️ Latence moy.", f"{int(row['latence_moy_ms'] or 0)} ms")
    else:
        st.info("ℹ️ Aucune conversation enregistrée pour le moment. Lance une simulation depuis l'interface !")

    st.divider()

    col1, col2 = st.columns(2)

    # Distribution des scores
    with col1:
        st.subheader("Distribution des scores qualité")
        df_scores = query("SELECT global_score FROM quality_evaluations WHERE global_score IS NOT NULL")
        if not df_scores.empty:
            fig = px.histogram(df_scores, x="global_score", nbins=20,
                               color_discrete_sequence=["#cba6f7"],
                               labels={"global_score": "Score /100", "count": "Nb conversations"})
            fig.update_layout(paper_bgcolor="#1e1e2e", plot_bgcolor="#1e1e2e",
                              font_color="#cdd6f4", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Pas encore de données")

    # Répartition OPTIMAL vs INTERVENTION
    with col2:
        st.subheader("Statut Workforce Manager")
        df_status = query("""
            SELECT status, COUNT(*) AS nb
            FROM workforce_decisions
            WHERE status IS NOT NULL
            GROUP BY status
        """)
        if not df_status.empty:
            colors = {"OPTIMAL": "#a6e3a1", "INTERVENTION_REQUISE": "#f38ba8"}
            fig = px.pie(df_status, names="status", values="nb",
                         color="status", color_discrete_map=colors,
                         hole=0.4)
            fig.update_layout(paper_bgcolor="#1e1e2e", font_color="#cdd6f4")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Pas encore de données")

    # Actions Workforce les plus déclenchées
    st.subheader("⚡ Actions les plus déclenchées par le Workforce Manager")
    df_actions = query("""
        SELECT
            COUNT(CASE WHEN has_escalation THEN 1 END)    AS escalade_humain,
            COUNT(CASE WHEN has_rag_relaunch THEN 1 END)  AS relancer_rag,
            COUNT(CASE WHEN has_kb_signal THEN 1 END)     AS signaler_kb,
            COUNT(CASE WHEN has_training THEN 1 END)      AS formation
        FROM workforce_decisions
    """)
    if not df_actions.empty:
        row = df_actions.iloc[0]
        actions_df = pd.DataFrame({
            "Action": ["Escalade humain", "Relancer RAG", "Signaler KB", "Formation"],
            "Nb déclenchements": [row["escalade_humain"], row["relancer_rag"],
                                   row["signaler_kb"], row["formation"]]
        })
        fig = px.bar(actions_df, x="Nb déclenchements", y="Action", orientation="h",
                     color_discrete_sequence=["#89b4fa"])
        fig.update_layout(paper_bgcolor="#1e1e2e", plot_bgcolor="#1e1e2e", font_color="#cdd6f4")
        st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# PAGE 2 — TENDANCES TEMPORELLES
# ════════════════════════════════════════════════════════════════════════════════
elif page == "📈 Tendances temporelles":
    st.title("📈 Tendances temporelles")

    df_daily = query("SELECT * FROM v_daily_kpis ORDER BY day ASC")

    if df_daily.empty:
        st.info("ℹ️ Pas encore de données journalières.")
    else:
        df_daily["day"] = pd.to_datetime(df_daily["day"])

        tab1, tab2, tab3 = st.tabs(["Score qualité", "Volume & Escalades", "Critères"])

        with tab1:
            fig = px.line(df_daily, x="day", y="avg_quality_score",
                          title="Évolution du score qualité moyen",
                          markers=True, color_discrete_sequence=["#cba6f7"])
            fig.add_hline(y=75, line_dash="dash", line_color="#f38ba8",
                          annotation_text="Seuil cible 75")
            fig.update_layout(paper_bgcolor="#1e1e2e", plot_bgcolor="#1e1e2e", font_color="#cdd6f4")
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_daily["day"], y=df_daily["nb_conversations"],
                                 name="Nb conversations", marker_color="#89b4fa"))
            fig.add_trace(go.Scatter(x=df_daily["day"], y=df_daily["escalation_rate_pct"],
                                     name="Taux escalade (%)", yaxis="y2",
                                     line=dict(color="#f38ba8", width=2)))
            fig.update_layout(
                title="Volume de simulations & taux d'escalade",
                yaxis2=dict(overlaying="y", side="right", title="Escalade (%)"),
                paper_bgcolor="#1e1e2e", plot_bgcolor="#1e1e2e", font_color="#cdd6f4"
            )
            st.plotly_chart(fig, use_container_width=True)

        with tab3:
            criteria_cols = ["avg_pertinence", "avg_empathie", "avg_clarte", "avg_conformite"]
            criteria_labels = {"avg_pertinence": "Pertinence", "avg_empathie": "Empathie",
                               "avg_clarte": "Clarté", "avg_conformite": "Conformité"}
            df_melt = df_daily[["day"] + criteria_cols].melt(id_vars="day",
                        var_name="Critère", value_name="Score")
            df_melt["Critère"] = df_melt["Critère"].map(criteria_labels)
            fig = px.line(df_melt, x="day", y="Score", color="Critère", markers=True,
                          title="Évolution des scores par critère")
            fig.update_layout(paper_bgcolor="#1e1e2e", plot_bgcolor="#1e1e2e", font_color="#cdd6f4")
            st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# PAGE 3 — ANALYSE PAR PROFIL
# ════════════════════════════════════════════════════════════════════════════════
elif page == "🎭 Analyse par profil":
    st.title("🎭 Performance par profil client")

    df_prof = query("SELECT * FROM v_profile_perf")

    if df_prof.empty:
        st.info("ℹ️ Pas encore de données par profil.")
    else:
        df_prof["profile_label"] = df_prof["profile"].map(
            lambda x: PROFILE_LABELS.get(x, x))
        df_prof["color"] = df_prof["profile"].map(
            lambda x: PROFILE_COLORS.get(x, "#cba6f7"))

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Score moyen par profil")
            fig = px.bar(df_prof.sort_values("avg_quality_score"),
                         x="avg_quality_score", y="profile_label",
                         orientation="h", color="profile",
                         color_discrete_map={k: PROFILE_COLORS.get(v.split(" ")[-1].lower(), "#cba6f7")
                                             for k, v in PROFILE_LABELS.items()},
                         labels={"avg_quality_score": "Score /100", "profile_label": "Profil"})
            fig.add_vline(x=75, line_dash="dash", line_color="#f38ba8")
            fig.update_layout(paper_bgcolor="#1e1e2e", plot_bgcolor="#1e1e2e",
                              font_color="#cdd6f4", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Taux d'escalade par profil")
            fig = px.bar(df_prof.sort_values("escalation_rate_pct", ascending=False),
                         x="profile_label", y="escalation_rate_pct",
                         color_discrete_sequence=["#f38ba8"],
                         labels={"escalation_rate_pct": "Escalade (%)", "profile_label": "Profil"})
            fig.update_layout(paper_bgcolor="#1e1e2e", plot_bgcolor="#1e1e2e", font_color="#cdd6f4")
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("📋 Tableau détaillé")
        df_display = df_prof[["profile_label", "nb_conversations", "avg_quality_score",
                               "avg_empathie", "avg_pertinence", "avg_conformite",
                               "escalation_rate_pct", "min_score", "max_score"]].copy()
        df_display.columns = ["Profil", "Nb conv.", "Score moy.", "Empathie",
                               "Pertinence", "Conformité", "Escalade %", "Min", "Max"]
        st.dataframe(df_display, use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════════════════════════
# PAGE 4 — CRITÈRES QUALITÉ
# ════════════════════════════════════════════════════════════════════════════════
elif page == "🔬 Critères qualité":
    st.title("🔬 Analyse des critères qualité")

    df_avg = query("""
        SELECT
            ROUND(AVG(score_pertinence)::NUMERIC, 1)   AS pertinence,
            ROUND(AVG(score_exactitude)::NUMERIC, 1)   AS exactitude,
            ROUND(AVG(score_groundedness)::NUMERIC, 1) AS groundedness,
            ROUND(AVG(score_empathie)::NUMERIC, 1)     AS empathie,
            ROUND(AVG(score_clarte)::NUMERIC, 1)       AS clarte,
            ROUND(AVG(score_conformite)::NUMERIC, 1)   AS conformite
        FROM quality_evaluations
    """)

    if not df_avg.empty and df_avg.iloc[0]["pertinence"] is not None:
        row = df_avg.iloc[0]
        criteria = {
            "Pertinence": row["pertinence"], "Exactitude": row["exactitude"],
            "Groundedness": row["groundedness"], "Empathie": row["empathie"],
            "Clarté": row["clarte"], "Conformité": row["conformite"],
        }
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Radar des critères moyens")
            cats = list(criteria.keys())
            vals = list(criteria.values())
            fig = go.Figure(go.Scatterpolar(
                r=[v for v in vals if v is not None],
                theta=cats, fill="toself",
                line_color="#cba6f7", fillcolor="rgba(203,166,247,0.2)"
            ))
            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                              paper_bgcolor="#1e1e2e", font_color="#cdd6f4")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Scores moyens par critère")
            df_bar = pd.DataFrame({"Critère": list(criteria.keys()),
                                   "Score": list(criteria.values())})
            df_bar = df_bar.dropna()
            colors = ["#f38ba8" if v < 75 else "#a6e3a1" for v in df_bar["Score"]]
            fig = px.bar(df_bar, x="Score", y="Critère", orientation="h",
                         color="Score", color_continuous_scale=["#f38ba8", "#f9e2af", "#a6e3a1"],
                         range_color=[0, 100])
            fig.add_vline(x=75, line_dash="dash", line_color="white")
            fig.update_layout(paper_bgcolor="#1e1e2e", plot_bgcolor="#1e1e2e", font_color="#cdd6f4")
            st.plotly_chart(fig, use_container_width=True)

        # Distribution par priorité
        st.subheader("Distribution par niveau de risque")
        df_priority = query("""
            SELECT priority, COUNT(*) AS nb FROM quality_evaluations
            WHERE priority IS NOT NULL GROUP BY priority
        """)
        if not df_priority.empty:
            color_map = {"faible": "#a6e3a1", "moyen": "#f9e2af",
                         "eleve": "#fab387", "critique": "#f38ba8"}
            fig = px.pie(df_priority, names="priority", values="nb",
                         color="priority", color_discrete_map=color_map, hole=0.4)
            fig.update_layout(paper_bgcolor="#1e1e2e", font_color="#cdd6f4")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("ℹ️ Pas encore de données qualité.")


# ════════════════════════════════════════════════════════════════════════════════
# PAGE 5 — ALERTES & ESCALADES
# ════════════════════════════════════════════════════════════════════════════════
elif page == "⚠️ Alertes & Escalades":
    st.title("⚠️ Alertes & Escalades")

    df_esc = query("SELECT * FROM v_escalation_log ORDER BY created_at DESC LIMIT 50")

    if df_esc.empty:
        st.success("✅ Aucune escalade critique enregistrée !")
    else:
        st.error(f"🚨 {len(df_esc)} conversation(s) escaladée(s) ou à risque élevé")
        for _, row in df_esc.iterrows():
            with st.expander(
                f"{'🔴' if row['priority'] == 'critique' else '🟠'} "
                f"{row['profile']} | Score: {row['global_score']}/100 | "
                f"{str(row['created_at'])[:16]}"
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Client :** {row['client_name']} ({row['client_age']} ans, {row['client_city']})")
                    st.write(f"**Thème :** {row['topic']} | **Urgence :** {row['urgency']}")
                    st.write(f"**Priorité :** `{row['priority']}`")
                    if row["alerts"]:
                        st.warning(f"⚠️ {row['alerts']}")
                with col2:
                    if row["problems"]:
                        st.write(f"**Problèmes :** {row['problems']}")
                    if row["action_types"]:
                        st.write(f"**Actions :** `{row['action_types']}`")
                    if row["staffing_impact"]:
                        st.write(f"**Impact staffing :** {row['staffing_impact']}")


# ════════════════════════════════════════════════════════════════════════════════
# PAGE 6 — CONVERSATIONS RÉCENTES
# ════════════════════════════════════════════════════════════════════════════════
elif page == "📋 Conversations récentes":
    st.title("📋 Conversations récentes")

    col1, col2, col3 = st.columns(3)
    with col1:
        profile_filter = st.selectbox("Filtrer par profil", ["Tous"] + list(PROFILE_LABELS.keys()))
    with col2:
        topic_filter = st.text_input("Filtrer par thème", "")
    with col3:
        limit = st.slider("Nb de conversations", 10, 100, 20)

    where = []
    params = []
    if profile_filter != "Tous":
        where.append("c.profile = %s")
        params.append(profile_filter)
    if topic_filter:
        where.append("c.topic ILIKE %s")
        params.append(f"%{topic_filter}%")

    where_clause = "WHERE " + " AND ".join(where) if where else ""

    df_conv = query(f"""
        SELECT
            c.id, c.created_at, c.profile, c.topic, c.urgency,
            c.client_name, c.client_age, c.completed_turns,
            q.global_score, q.priority, q.requires_human_review,
            w.status AS workforce_status, w.action_types
        FROM sim_conversations c
        LEFT JOIN quality_evaluations q ON q.conversation_id = c.id
        LEFT JOIN workforce_decisions w ON w.conversation_id = c.id
        {where_clause}
        ORDER BY c.created_at DESC
        LIMIT %s
    """, params + [limit])

    if df_conv.empty:
        st.info("Aucune conversation trouvée.")
    else:
        df_conv["Profil"] = df_conv["profile"].map(lambda x: PROFILE_LABELS.get(x, x))
        df_conv["Score"] = df_conv["global_score"].apply(
            lambda x: f"🟢 {x}" if x and x >= 75 else (f"🟠 {x}" if x and x >= 60 else f"🔴 {x}") if x else "—")
        df_conv["Statut WF"] = df_conv["workforce_status"].map(
            {"OPTIMAL": "✅ Optimal", "INTERVENTION_REQUISE": "⚠️ Intervention"}).fillna("—")

        display_cols = {
            "created_at": "Date", "Profil": "Profil", "topic": "Thème",
            "client_name": "Client", "completed_turns": "Tours",
            "Score": "Score", "priority": "Risque", "Statut WF": "Workforce"
        }
        st.dataframe(
            df_conv[list(display_cols.keys())].rename(columns=display_cols),
            use_container_width=True, hide_index=True
        )

        # Drill-down
        st.subheader("🔍 Détail d'une conversation")
        conv_ids = df_conv["id"].tolist()
        selected_id = st.selectbox("Sélectionner une conversation", conv_ids)
        if selected_id:
            df_turns = query("""
                SELECT turn, role, content, word_count, latency_ms, intent, urgent
                FROM sim_turns WHERE conversation_id = %s ORDER BY turn, role
            """, [selected_id])
            if not df_turns.empty:
                for _, turn in df_turns.iterrows():
                    icon = "👤" if turn["role"] == "client" else "🤖"
                    with st.chat_message("human" if turn["role"] == "client" else "assistant"):
                        st.write(f"**Tour {int(turn['turn'])}** {icon}")
                        st.write(turn["content"])
                        st.caption(f"Mots: {turn['word_count']} | Latence: {turn['latency_ms']} ms | Intent: {turn['intent']}")
