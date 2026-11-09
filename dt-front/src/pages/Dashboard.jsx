import { useEffect, useState, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, ArcElement, RadialLinearScale, Filler,
  Title, Tooltip, Legend,
} from 'chart.js'
import { Line, Bar, Doughnut, Radar } from 'react-chartjs-2'
import {
  BarChart2, TrendingUp, Users, AlertTriangle, CheckCircle,
  Clock, Zap, RefreshCw, ArrowUpRight, ArrowDownRight,
} from 'lucide-react'
import { api } from '../api/client'

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, ArcElement, RadialLinearScale, Filler,
  Title, Tooltip, Legend
)

// ── Palette & Labels ──────────────────────────────────────────────────────────
const PROFILE_LABELS = {
  calme: 'Calme', impatient: 'Impatient', nerveux: 'Nerveux',
  mecontent: 'Mécontent', fidele: 'Fidèle', confus: 'Confus',
  exigeant: 'Exigeant', heureux: 'Heureux',
}
const PROFILE_EMOJI = {
  calme: '😌', impatient: '⚡', nerveux: '😰',
  mecontent: '😠', fidele: '⭐', confus: '❓',
  exigeant: '💼', heureux: '😊',
}
const PROFILE_COLORS = [
  '#8b5cf6','#f97316','#ef4444','#3b82f6',
  '#22c55e','#eab308','#ec4899','#06b6d4',
]
const CRITERIA_COLORS = ['#8b5cf6','#3b82f6','#06b6d4','#f43f5e','#22c55e','#f97316']

const CHART_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
}
const GRID_STYLE = {
  color: 'rgba(0,0,0,0.05)',
  drawBorder: false,
}
const TICK_STYLE = {
  color: '#8a8a96',
  font: { family: 'Inter, sans-serif', size: 11 },
}

const scoreColor = (s) =>
  s == null ? 'var(--muted)' : s >= 75 ? '#16a34a' : s >= 60 ? '#ea580c' : '#dc2626'

const scoreBg = (s) =>
  s == null ? '#f3f4f6' : s >= 75 ? '#dcfce7' : s >= 60 ? '#fff7ed' : '#fef2f2'

// ── KPI Card ──────────────────────────────────────────────────────────────────
function KpiCard({ label, value, unit = '', icon: Icon, color = '#8b5cf6', sub, trend }) {
  return (
    <div className="card" style={{ padding: '18px 20px', position: 'relative', overflow: 'hidden' }}>
      <div style={{
        position: 'absolute', top: 0, right: 0, width: 80, height: 80,
        background: `radial-gradient(circle at 70% 30%, ${color}18, transparent 70%)`,
        borderRadius: '0 14px 0 80px',
      }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 500 }}>{label}</span>
        <span style={{ background: `${color}18`, borderRadius: 8, padding: '5px 7px', display: 'grid', placeItems: 'center' }}>
          <Icon size={15} color={color} />
        </span>
      </div>
      <div style={{ fontSize: 32, fontWeight: 700, letterSpacing: '-.03em', color: 'var(--text)', lineHeight: 1 }}>
        {value != null ? value : '—'}
        {value != null && <small style={{ fontSize: 14, color: 'var(--muted)', fontWeight: 500, marginLeft: 4 }}>{unit}</small>}
      </div>
      {(sub || trend != null) && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8 }}>
          {trend != null && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 12,
              color: trend >= 0 ? '#16a34a' : '#dc2626', fontWeight: 600 }}>
              {trend >= 0 ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
              {Math.abs(trend)}%
            </span>
          )}
          {sub && <span style={{ fontSize: 12, color: 'var(--muted)' }}>{sub}</span>}
        </div>
      )}
    </div>
  )
}

// ── Section Header ────────────────────────────────────────────────────────────
function SectionTitle({ children }) {
  return (
    <h3 style={{ margin: '0 0 14px', fontSize: 14, fontWeight: 600, color: 'var(--text)',
      display: 'flex', alignItems: 'center', gap: 8 }}>
      {children}
    </h3>
  )
}

// ── Chart Card wrapper ────────────────────────────────────────────────────────
function ChartCard({ title, children, height = 220, style = {} }) {
  return (
    <div className="panel" style={{ ...style }}>
      <SectionTitle>{title}</SectionTitle>
      <div style={{ height, position: 'relative' }}>{children}</div>
    </div>
  )
}

// ── Score Badge ───────────────────────────────────────────────────────────────
function ScoreBadge({ score }) {
  if (score == null) return <span style={{ color: 'var(--muted)' }}>—</span>
  return (
    <span style={{
      background: scoreBg(score), color: scoreColor(score),
      fontWeight: 700, borderRadius: 6, padding: '2px 9px', fontSize: 12,
    }}>{score}/100</span>
  )
}

// ── Main Dashboard ────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [kpis, setKpis]             = useState(null)
  const [criteria, setCriteria]     = useState([])
  const [profiles, setProfiles]     = useState([])
  const [trends, setTrends]         = useState([])
  const [wfStats, setWfStats]       = useState(null)
  const [alerts, setAlerts]         = useState([])
  const [conversations, setConvs]   = useState([])
  const [topics, setTopics]         = useState([])
  const [clientDist, setClientDist] = useState([])
  const [loading, setLoading]       = useState(true)
  const [activeTab, setActiveTab]   = useState('overview')
  const [lastRefresh, setLastRefresh] = useState(new Date())

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [k, cr, pr, tr, wf, al, cv, tp, cd] = await Promise.all([
        api.getDashboardKpis(),
        api.getDashboardCriteria(),
        api.getDashboardProfiles(),
        api.getDashboardTrends(),
        api.getDashboardWorkforce(),
        api.getDashboardAlerts(15),
        api.getDashboardConversations(25),
        api.getDashboardTopics(),
        api.getDashboardClientDistribution(),
      ])
      setKpis(k); setCriteria(cr); setProfiles(pr); setTrends(tr)
      setWfStats(wf); setAlerts(al); setConvs(cv); setTopics(tp); setClientDist(cd)
      setLastRefresh(new Date())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => { const id = setInterval(load, 30000); return () => clearInterval(id) }, [load])

  // ── Chart data builders ───────────────────────────────────────────────────
  const trendLineData = {
    labels: trends.map(d => d.day?.slice(5)),
    datasets: [{
      label: 'Score qualité', data: trends.map(d => d.scoreMoyen),
      borderColor: '#8b5cf6', backgroundColor: 'rgba(139,92,246,.1)',
      tension: 0.4, fill: true, pointRadius: 3, pointHoverRadius: 6,
      borderWidth: 2.5,
    }, {
      label: 'Cible 75', data: trends.map(() => 75),
      borderColor: '#ef4444', borderDash: [5, 4], borderWidth: 1.5,
      pointRadius: 0, fill: false,
    }],
  }

  const volumeBarData = {
    labels: trends.map(d => d.day?.slice(5)),
    datasets: [{
      label: 'Conversations', data: trends.map(d => d.nbConversations),
      backgroundColor: 'rgba(139,92,246,.7)', borderRadius: 6,
      borderColor: '#8b5cf6', borderWidth: 1,
    }],
  }

  const escaladeLineData = {
    labels: trends.map(d => d.day?.slice(5)),
    datasets: [{
      label: 'Taux escalade (%)', data: trends.map(d => d.escaladeRate),
      borderColor: '#f97316', backgroundColor: 'rgba(249,115,22,.1)',
      tension: 0.4, fill: true, pointRadius: 3, borderWidth: 2,
    }],
  }

  const profileDoughnutData = {
    labels: clientDist.map(d => `${PROFILE_EMOJI[d.profile] || ''} ${PROFILE_LABELS[d.profile] || d.profile}`),
    datasets: [{
      data: clientDist.map(d => d.pctConversations),
      backgroundColor: PROFILE_COLORS.slice(0, clientDist.length),
      borderWidth: 2, borderColor: '#fff',
      hoverOffset: 8,
    }],
  }

  const wfDoughnutData = wfStats ? {
    labels: ['Optimal', 'Intervention'],
    datasets: [{
      data: [wfStats.optimal, wfStats.intervention],
      backgroundColor: ['#22c55e', '#f97316'],
      borderWidth: 2, borderColor: '#fff', hoverOffset: 8,
    }],
  } : null

  const criteriaBarData = {
    labels: criteria.map(c => c.criterion),
    datasets: [{
      label: 'Score moyen',
      data: criteria.map(c => c.score),
      backgroundColor: criteria.map((c, i) => `${CRITERIA_COLORS[i]}cc`),
      borderColor: CRITERIA_COLORS,
      borderWidth: 2, borderRadius: 8,
    }],
  }

  const radarData = {
    labels: criteria.map(c => c.criterion),
    datasets: [{
      label: 'Score moyen',
      data: criteria.map(c => c.score),
      borderColor: '#8b5cf6', backgroundColor: 'rgba(139,92,246,.15)',
      pointBackgroundColor: CRITERIA_COLORS,
      pointBorderColor: '#fff', pointRadius: 5,
      borderWidth: 2,
    }],
  }

  const profileBarData = {
    labels: profiles.map(p => `${PROFILE_EMOJI[p.profile] || ''} ${PROFILE_LABELS[p.profile] || p.profile}`),
    datasets: [{
      label: 'Score qualité moyen',
      data: profiles.map(p => p.score),
      backgroundColor: profiles.map((_, i) => `${PROFILE_COLORS[i % PROFILE_COLORS.length]}cc`),
      borderColor: profiles.map((_, i) => PROFILE_COLORS[i % PROFILE_COLORS.length]),
      borderWidth: 2, borderRadius: 8,
    }],
  }

  const topicBarData = {
    labels: topics.map(t => t.topic),
    datasets: [{
      label: 'Score qualité', data: topics.map(t => t.score),
      backgroundColor: 'rgba(59,130,246,.7)', borderColor: '#3b82f6',
      borderWidth: 2, borderRadius: 6,
    }],
  }

  // ── Chart options ─────────────────────────────────────────────────────────
  const lineOpts = {
    ...CHART_DEFAULTS,
    plugins: {
      legend: { display: true, position: 'top', labels: { font: { family: 'Inter', size: 11 }, boxWidth: 14, padding: 16 } },
      tooltip: { backgroundColor: '#111114', titleFont: { family: 'Inter' }, bodyFont: { family: 'Inter' } },
    },
    scales: {
      x: { grid: GRID_STYLE, ticks: { ...TICK_STYLE, maxTicksLimit: 10 } },
      y: { grid: GRID_STYLE, ticks: TICK_STYLE, min: 0 },
    },
  }

  const barOpts = {
    ...CHART_DEFAULTS,
    plugins: {
      legend: { display: false },
      tooltip: { backgroundColor: '#111114', titleFont: { family: 'Inter' }, bodyFont: { family: 'Inter' } },
    },
    scales: {
      x: { grid: { display: false }, ticks: TICK_STYLE },
      y: { grid: GRID_STYLE, ticks: TICK_STYLE },
    },
  }

  const hBarOpts = {
    ...barOpts,
    indexAxis: 'y',
    scales: {
      x: { grid: GRID_STYLE, ticks: TICK_STYLE, min: 0, max: 100 },
      y: { grid: { display: false }, ticks: { ...TICK_STYLE, font: { family: 'Inter', size: 12 } } },
    },
  }

  const doughnutOpts = {
    ...CHART_DEFAULTS,
    cutout: '65%',
    plugins: {
      legend: {
        display: true, position: 'right',
        labels: { font: { family: 'Inter', size: 12 }, boxWidth: 12, padding: 14, color: '#2b2b31' },
      },
      tooltip: {
        backgroundColor: '#111114',
        callbacks: { label: (ctx) => ` ${ctx.label}: ${ctx.parsed}%` },
      },
    },
  }

  const radarOpts = {
    ...CHART_DEFAULTS,
    plugins: {
      legend: { display: false },
      tooltip: { backgroundColor: '#111114', bodyFont: { family: 'Inter' } },
    },
    scales: {
      r: {
        min: 0, max: 100,
        grid: { color: 'rgba(0,0,0,0.07)' },
        ticks: { backdropColor: 'transparent', color: '#8a8a96', font: { size: 10 } },
        pointLabels: { font: { family: 'Inter', size: 12 }, color: '#2b2b31' },
      },
    },
  }

  const TABS = [
    { id: 'overview',  label: '📊 Vue globale' },
    { id: 'trends',    label: '📈 Tendances' },
    { id: 'clients',   label: '👥 Clients' },
    { id: 'quality',   label: '🔬 Qualité' },
    { id: 'alerts',    label: `⚠️ Alertes${alerts.length ? ` (${alerts.length})` : ''}` },
    { id: 'convs',     label: '📋 Conversations' },
  ]

  return (
    <div style={{ maxWidth: 1140, margin: '0 auto' }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 22 }}>
        <div>
          <h1 className="page-title" style={{ fontSize: 22 }}>💊 Dashboard BI — PharmaShop Digital Twin</h1>
          <p className="page-sub" style={{ marginBottom: 0 }}>
            Mis à jour · {lastRefresh.toLocaleTimeString('fr-FR')}
          </p>
        </div>
        <button onClick={load} style={{ display: 'flex', alignItems: 'center', gap: 6,
          border: '1px solid var(--border)', background: '#fff', borderRadius: 10,
          padding: '8px 16px', fontSize: 13, cursor: 'pointer', fontWeight: 500 }}>
          <RefreshCw size={14} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          Rafraîchir
        </button>
      </div>

      {/* ── Tabs ── */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 24, borderBottom: '1px solid var(--border)', overflowX: 'auto' }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)} style={{
            border: 'none', background: 'none', padding: '10px 18px', fontSize: 13,
            cursor: 'pointer', whiteSpace: 'nowrap', fontWeight: activeTab === t.id ? 600 : 400,
            color: activeTab === t.id ? 'var(--violet-strong)' : 'var(--muted)',
            borderBottom: `2px solid ${activeTab === t.id ? 'var(--violet-strong)' : 'transparent'}`,
          }}>{t.label}</button>
        ))}
      </div>

      {loading && !kpis && (
        <div className="empty-state">
          <div className="typing" style={{ justifyContent: 'center', marginBottom: 14 }}><i /><i /><i /></div>
          Chargement des données…
        </div>
      )}

      {/* ════════ OVERVIEW ════════ */}
      {activeTab === 'overview' && kpis && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* KPI Row 1 — conversations & qualité */}
          <div className="kpis">
            <KpiCard label="Total conversations" value={kpis.nbConversations} icon={BarChart2} color="#8b5cf6" sub="sessions simulées" />
            <KpiCard label="Score qualité moyen" value={kpis.scoreMoyen} unit="/100" icon={TrendingUp} color={scoreColor(kpis.scoreMoyen)} sub="évaluations Gemini" />
            <KpiCard label="Taux de résolution" value={kpis.tauxResolution} unit="%" icon={CheckCircle} color="#22c55e" sub="statut OPTIMAL" />
            <KpiCard label="Taux d'escalade" value={kpis.tauxEscalade} unit="%" icon={AlertTriangle} color="#f97316" sub="conversations escaladées" />
            <KpiCard label="Alertes critiques" value={kpis.alertesCritiques} icon={Zap} color="#ef4444" sub="priority critique" />
            <KpiCard label="Latence conseiller" value={kpis.latenceMoyMs} unit=" ms" icon={Clock} color="#3b82f6" sub="moyenne par session" />
          </div>

          {/* Charts row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 16 }}>
            <ChartCard title="📈 Score qualité — 30 derniers jours" height={220}>
              <Line data={trendLineData} options={{
                ...lineOpts,
                plugins: { ...lineOpts.plugins, legend: { display: true, position: 'top',
                  labels: { font: { family: 'Inter', size: 11 }, boxWidth: 12, padding: 12 } } }
              }} />
            </ChartCard>
            <ChartCard title="⚙️ Statut Workforce Manager" height={220}>
              {wfDoughnutData ? <Doughnut data={wfDoughnutData} options={doughnutOpts} /> :
                <p className="page-sub">Pas de données</p>}
            </ChartCard>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <ChartCard title="📦 Volume de conversations par jour" height={180}>
              <Bar data={volumeBarData} options={barOpts} />
            </ChartCard>
            <ChartCard title="🚨 Taux d'escalade (%)" height={180}>
              <Line data={escaladeLineData} options={{ ...lineOpts, plugins: { ...lineOpts.plugins, legend: { display: false } } }} />
            </ChartCard>
          </div>

          {/* Workforce actions */}
          {wfStats && wfStats.total > 0 && (
            <div className="panel">
              <SectionTitle>⚡ Actions déclenchées par le Workforce Manager</SectionTitle>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {wfStats.actions.map((a, i) => (
                  <div key={a.type} style={{ textAlign: 'center', padding: '14px 10px',
                    background: '#f8f7ff', borderRadius: 12, border: '1px solid var(--violet-border)' }}>
                    <div style={{ fontSize: 28, fontWeight: 700, color: PROFILE_COLORS[i] }}>{a.nb}</div>
                    <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>{a.type}</div>
                    <div style={{ height: 4, background: 'var(--border)', borderRadius: 99, marginTop: 8 }}>
                      <div style={{ height: '100%', width: `${(a.nb / wfStats.total) * 100}%`,
                        background: PROFILE_COLORS[i], borderRadius: 99 }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ════════ TENDANCES ════════ */}
      {activeTab === 'trends' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <ChartCard title="Score qualité moyen (30 jours)" height={260}>
            <Line data={trendLineData} options={lineOpts} />
          </ChartCard>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <ChartCard title="Volume de conversations par jour" height={200}>
              <Bar data={volumeBarData} options={barOpts} />
            </ChartCard>
            <ChartCard title="Taux d'escalade (%)" height={200}>
              <Line data={escaladeLineData} options={{ ...lineOpts, plugins: { ...lineOpts.plugins, legend: { display: false } } }} />
            </ChartCard>
          </div>

          {/* Tableau journalier */}
          <div className="panel">
            <SectionTitle>📋 Données journalières</SectionTitle>
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Date</th><th>Conversations</th><th>Score moy.</th>
                    <th>Empathie</th><th>Pertinence</th><th>Escalades</th><th>Résolution %</th>
                  </tr>
                </thead>
                <tbody>
                  {[...trends].reverse().map(d => (
                    <tr key={d.day} className="hist-row">
                      <td style={{ fontWeight: 500 }}>{d.day}</td>
                      <td>{d.nbConversations}</td>
                      <td><ScoreBadge score={d.scoreMoyen} /></td>
                      <td>{d.empathie ?? '—'}</td>
                      <td>{d.pertinence ?? '—'}</td>
                      <td style={{ color: d.nbEscalades > 0 ? '#f97316' : 'inherit' }}>{d.nbEscalades}</td>
                      <td style={{ color: d.resolutionRate >= 70 ? '#16a34a' : '#dc2626' }}>
                        {d.resolutionRate ?? '—'}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ════════ CLIENTS ════════ */}
      {activeTab === 'clients' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Distribution doughnut + KPIs profils */}
          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 16 }}>
            <ChartCard title="🎭 Répartition des conversations par profil client" height={260}>
              {clientDist.length > 0
                ? <Doughnut data={profileDoughnutData} options={doughnutOpts} />
                : <p className="page-sub">Pas de données</p>}
            </ChartCard>

            <div className="panel">
              <SectionTitle>📊 Détail par profil</SectionTitle>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 280, overflowY: 'auto' }}>
                {clientDist.map((d, i) => (
                  <div key={d.profile} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 18 }}>{PROFILE_EMOJI[d.profile]}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span style={{ fontSize: 13, fontWeight: 600 }}>{PROFILE_LABELS[d.profile] || d.profile}</span>
                        <span style={{ fontSize: 13, fontWeight: 700, color: PROFILE_COLORS[i % 8] }}>
                          {d.pctConversations}%
                        </span>
                      </div>
                      <div style={{ height: 6, background: 'var(--border)', borderRadius: 99, overflow: 'hidden' }}>
                        <div style={{ width: `${d.pctConversations}%`, height: '100%',
                          background: PROFILE_COLORS[i % 8], borderRadius: 99,
                          transition: 'width .4s ease' }} />
                      </div>
                      <span style={{ fontSize: 11, color: 'var(--muted)' }}>{d.nbConversations} conversations</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Score moyen par profil (bar horizontal) */}
          <ChartCard title="⭐ Score qualité moyen par profil" height={220}>
            <Bar data={profileBarData} options={hBarOpts} />
          </ChartCard>

          {/* Tableau thématiques */}
          <ChartCard title="🗂️ Analyse par thématique" height={220}>
            <Bar data={topicBarData} options={{
              ...barOpts,
              scales: {
                ...barOpts.scales,
                x: { grid: { display: false }, ticks: { ...TICK_STYLE, maxRotation: 30 } },
                y: { grid: GRID_STYLE, ticks: TICK_STYLE, min: 0, max: 100 },
              },
            }} />
          </ChartCard>

          {/* Tableau profils */}
          <div className="panel">
            <SectionTitle>📋 Tableau de performance par profil</SectionTitle>
            <table className="table">
              <thead>
                <tr>
                  <th>Profil</th><th>Conversations</th><th>Score moy.</th>
                  <th>Empathie</th><th>Pertinence</th><th>Conformité</th><th>Escalade %</th>
                </tr>
              </thead>
              <tbody>
                {profiles.map(p => (
                  <tr key={p.profile} className="hist-row">
                    <td>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 16 }}>{PROFILE_EMOJI[p.profile]}</span>
                        <strong>{PROFILE_LABELS[p.profile] || p.profile}</strong>
                      </span>
                    </td>
                    <td>{p.nb}</td>
                    <td><ScoreBadge score={p.score} /></td>
                    <td>{p.empathie ?? '—'}</td>
                    <td>{p.pertinence ?? '—'}</td>
                    <td>{p.conformite ?? '—'}</td>
                    <td style={{ color: p.escaladeRate > 20 ? '#dc2626' : p.escaladeRate > 10 ? '#ea580c' : '#16a34a', fontWeight: 600 }}>
                      {p.escaladeRate ?? '—'}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ════════ QUALITÉ ════════ */}
      {activeTab === 'quality' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <ChartCard title="🕸️ Radar des critères qualité" height={280}>
              {criteria.length > 0
                ? <Radar data={radarData} options={radarOpts} />
                : <p className="page-sub">Pas de données</p>}
            </ChartCard>
            <ChartCard title="📊 Score moyen par critère (/100)" height={280}>
              <Bar data={criteriaBarData} options={{
                ...hBarOpts,
                scales: {
                  x: { grid: GRID_STYLE, ticks: TICK_STYLE, min: 0, max: 100 },
                  y: { grid: { display: false }, ticks: { ...TICK_STYLE, font: { family: 'Inter', size: 12 } } },
                },
                plugins: {
                  ...hBarOpts.plugins,
                  tooltip: {
                    backgroundColor: '#111114',
                    callbacks: { label: (ctx) => ` ${ctx.parsed.x}/100` },
                  },
                },
              }} />
            </ChartCard>
          </div>

          {/* Scores en cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            {criteria.map((c, i) => (
              <div key={c.criterion} style={{
                background: '#fff', border: '1px solid var(--border)', borderRadius: 12, padding: '14px 16px',
                borderLeft: `4px solid ${CRITERIA_COLORS[i]}`,
              }}>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>{c.criterion}</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: scoreColor(c.score) }}>
                  {c.score ?? '—'}<small style={{ fontSize: 13, color: 'var(--muted)', marginLeft: 2 }}>/100</small>
                </div>
                <div style={{ marginTop: 8, height: 5, background: 'var(--border)', borderRadius: 99 }}>
                  <div style={{ width: `${c.score || 0}%`, height: '100%',
                    background: scoreColor(c.score), borderRadius: 99 }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ════════ ALERTES ════════ */}
      {activeTab === 'alerts' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {alerts.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon" style={{ background: '#dcfce7' }}>
                <CheckCircle size={28} color="#22c55e" />
              </div>
              <h4>Aucune escalade critique</h4>
              <p>Toutes les conversations sont dans les seuils acceptables.</p>
            </div>
          ) : alerts.map((a, i) => (
            <div key={a.conversationId + i} className="panel" style={{
              borderLeft: `4px solid ${a.priority === 'critique' ? '#ef4444' : '#f97316'}`,
              padding: '14px 18px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 6 }}>
                    <span className="tag">{PROFILE_EMOJI[a.profile]} {PROFILE_LABELS[a.profile] || a.profile}</span>
                    <span className="tag">{a.topic}</span>
                    <span style={{ background: a.priority === 'critique' ? '#fef2f2' : '#fff7ed',
                      color: a.priority === 'critique' ? '#dc2626' : '#ea580c',
                      padding: '1px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700,
                      textTransform: 'uppercase' }}>{a.priority}</span>
                  </div>
                  <div style={{ fontSize: 13, marginBottom: 6 }}>
                    <strong>{a.clientName}</strong>
                    {a.globalScore != null && <> · Score : <ScoreBadge score={a.globalScore} /></>}
                    <span style={{ color: 'var(--muted)', marginLeft: 8, fontSize: 12 }}>
                      {a.createdAt?.slice(0, 16).replace('T', ' ')}
                    </span>
                  </div>
                  {a.alerts && (
                    <div className="alert-item" style={{ fontSize: 12, marginBottom: 0 }}>
                      <AlertTriangle size={12} /> {a.alerts}
                    </div>
                  )}
                </div>
                {a.actionTypes && (
                  <div style={{ textAlign: 'right', fontSize: 11, color: 'var(--muted)', minWidth: 140 }}>
                    <div style={{ fontWeight: 600, marginBottom: 4 }}>Actions déclenchées</div>
                    <code style={{ fontSize: 11, background: '#f1f1f4', padding: '2px 6px', borderRadius: 4 }}>
                      {a.actionTypes}
                    </code>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ════════ CONVERSATIONS ════════ */}
      {activeTab === 'convs' && (
        <div className="panel">
          <SectionTitle>📋 Dernières conversations enregistrées</SectionTitle>
          {conversations.length === 0 ? (
            <div className="empty-state">
              <p>Pas encore de conversations. Lance une simulation !</p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Date</th><th>Profil</th><th>Thème</th><th>Client</th>
                    <th>Tours</th><th>Latence</th><th>Score</th><th>Priorité</th><th>Workforce</th>
                  </tr>
                </thead>
                <tbody>
                  {conversations.map((c, i) => (
                    <tr key={c.id + i} className="hist-row">
                      <td style={{ fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                        {c.createdAt?.slice(0, 16).replace('T', ' ')}
                      </td>
                      <td>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap' }}>
                          <span>{PROFILE_EMOJI[c.profile]}</span>
                          <span style={{ fontSize: 12, fontWeight: 500 }}>{PROFILE_LABELS[c.profile] || c.profile}</span>
                        </span>
                      </td>
                      <td><span className="tag" style={{ fontSize: 10 }}>{c.topic || '—'}</span></td>
                      <td style={{ fontSize: 12, whiteSpace: 'nowrap' }}>{c.clientName || '—'}</td>
                      <td style={{ textAlign: 'center' }}>{c.completedTurns ?? '—'}</td>
                      <td style={{ fontSize: 12, color: 'var(--muted)' }}>
                        {c.totalLatencyMs ? `${c.totalLatencyMs} ms` : '—'}
                      </td>
                      <td><ScoreBadge score={c.globalScore} /></td>
                      <td>
                        <span style={{ fontSize: 11, fontWeight: 600,
                          color: c.priority === 'critique' ? '#dc2626' : c.priority === 'eleve' ? '#ea580c' :
                                 c.priority === 'moyen' ? '#ca8a04' : '#16a34a' }}>
                          {c.priority || '—'}
                        </span>
                      </td>
                      <td style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                        <span style={{ color: c.workforceStatus === 'OPTIMAL' ? '#16a34a' : '#ea580c', fontWeight: 600 }}>
                          {c.workforceStatus === 'OPTIMAL' ? '✅ Optimal'
                           : c.workforceStatus === 'INTERVENTION_REQUISE' ? '⚠️ Intervention'
                           : '—'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

    </div>
  )
}
