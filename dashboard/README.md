# Dashboard BI — PharmaShop Digital Twin

Dashboard Streamlit connecté directement à PostgreSQL `callverse`.

## Lancement

```powershell
cd C:\Users\samar\Desktop\PI
.venv\Scripts\Activate.ps1
pip install streamlit plotly
cd dashboard
streamlit run app.py
```

→ Ouvre automatiquement **http://localhost:8501**

## Pages disponibles

| Page | Contenu |
|------|---------|
| 📊 Vue globale | 6 KPIs + distribution scores + statut Workforce + actions déclenchées |
| 📈 Tendances temporelles | Score qualité / volume / escalades dans le temps + critères |
| 🎭 Analyse par profil | Score & escalade par profil client (calme, nerveux...) |
| 🔬 Critères qualité | Radar spider + scores détaillés par critère (pertinence, empathie...) |
| ⚠️ Alertes & Escalades | Journal des conversations escaladées ou à risque élevé |
| 📋 Conversations récentes | Tableau filtrable + drill-down tour par tour |

## Source de données

Toutes les données viennent de PostgreSQL `callverse` via les vues :
- `v_bi_full` — jointure 360° conversations + qualité + workforce
- `v_daily_kpis` — agrégats journaliers
- `v_profile_perf` — performance par profil
- `v_escalation_log` — journal des escalades
