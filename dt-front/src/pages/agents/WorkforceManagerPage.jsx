import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Users, AlertTriangle, CheckCircle2, RefreshCw, Sliders, ArrowRight, ShieldAlert, Sparkles, UserCheck, BookOpen } from 'lucide-react'
import { api } from '../../api/client'

const WORKFORCE_PRESETS = [
  {
    name: 'Scénario Critique · Escalade Humaine N2 requise',
    score: 62,
    empathie: 55,
    groundedness: 60,
    profile: 'mecontent',
    desc: 'Score inférieur au seuil 75, fort mécontentement client sans solution.',
  },
  {
    name: 'Scénario Modéré · Ajustement de prompt & formation',
    score: 72,
    empathie: 65,
    groundedness: 82,
    profile: 'impatient',
    desc: 'Réponse correcte mais formulation trop rigide nécessitant une correction de ton.',
  },
  {
    name: 'Scénario Optimal · Conforme et autonome',
    score: 91,
    empathie: 90,
    groundedness: 94,
    profile: 'calme',
    desc: 'Traitement 100% réussi sans intervention de l’équipe de supervision.',
  },
]

const PRIO_META = {
  haute:   { icon: '▲', label: 'Haute',   color: '#be123c', bg: '#ffe4e6' },
  moyenne: { icon: '◆', label: 'Moyenne', color: '#b45309', bg: '#fef3c7' },
  basse:   { icon: '●', label: 'Basse',   color: '#0369a1', bg: '#e0f2fe' },
}

const fmt = (v, unit) => (v == null ? '—' : `${v}${unit}`) // KPI non mesuré = tiret

export default function WorkforceManagerPage() {
  const location = useLocation()
  const navigate = useNavigate()

  const prefilled = location.state?.prefilledEvaluation

  const [score, setScore] = useState(prefilled?.evaluation?.globalScore ?? 68)
  const [empathie, setEmpathie] = useState(prefilled?.evaluation?.criteria?.empathie ?? 60)
  const [groundedness, setGroundedness] = useState(prefilled?.evaluation
    ? prefilled.evaluation.criteria?.groundedness ?? null // null = non vérifié par l'Analyste Qualité
    : 65)
  const [profile, setProfile] = useState(prefilled?.request?.profile || 'mecontent')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [kpi, setKpi] = useState(null)

  useEffect(() => {
    api.getKpi().then(setKpi).catch(() => {})
  }, [])

  useEffect(() => {
    if (prefilled) {
      if (prefilled.evaluation?.globalScore !== undefined) setScore(prefilled.evaluation.globalScore)
      if (prefilled.evaluation?.criteria?.empathie !== undefined) setEmpathie(prefilled.evaluation.criteria.empathie)
      if (prefilled.evaluation?.criteria?.groundedness !== undefined) setGroundedness(prefilled.evaluation.criteria.groundedness ?? null)
      if (prefilled.request?.profile) setProfile(prefilled.request.profile)
    }
  }, [prefilled])

  const handleRunDecisions = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.runWorkforceManager({
        evaluation: {
          // signaux du rapport de l'Analyste Qualité (alertes, revue humaine, LoRA) transmis tels quels
          alerts: prefilled?.evaluation?.alerts,
          priority: prefilled?.evaluation?.priority,
          requiresHumanReview: prefilled?.evaluation?.requiresHumanReview,
          loraRisk: prefilled?.evaluation?.loraRisk,
          globalScore: Number(score),
          criteria: {
            ...prefilled?.evaluation?.criteria,
            empathie: empathie == null ? null : Number(empathie),
            groundedness: groundedness == null ? null : Number(groundedness),
          },
        },
        request: { profile },
        kpi,
      })
      setResult(data)
    } catch (e) {
      setError(e.message || 'Erreur lors de la prise de décisions')
    } finally {
      setLoading(false)
    }
  }

  const handleApplyPreset = (p) => {
    setScore(p.score)
    setEmpathie(p.empathie)
    setGroundedness(p.groundedness)
    setProfile(p.profile)
    setResult(null)
  }

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* Banner */}
      <div className="agent-banner" style={{ borderColor: 'rgba(245, 158, 11, 0.3)' }}>
        <div className="agent-badge-icon" style={{ background: '#fef3c7', color: '#b45309' }}>
          <Users size={26} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span className="agent-step-tag" style={{ background: '#fef3c7', color: '#92400e' }}>
              Agent 4 sur 4 · Pilotage & Décisions RH
            </span>
          </div>
          <h1 className="agent-title">Workforce Manager Agent</h1>
          <p className="agent-desc">
            Surveille la qualité globale, déclenche les escalades vers des conseillers humains, ajuste les consignes d'équipe et orchestre la formation continue.
          </p>
        </div>
      </div>

      {prefilled && (
        <div className="injected-alert">
          <CheckCircle2 size={16} color="#b45309" />
          <span>Évaluation injectée avec succès depuis l'agent <strong>Quality Analyst</strong> (Score : {score}/100).</span>
        </div>
      )}

      <div className="agent-grid">
        {/* Controls Column */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <h5>
            <Sliders size={16} color="#b45309" /> Données d'évaluation et seuils de contrôle
          </h5>

          {/* Presets */}
          <div>
            <label className="field-label">Scénarios prédéfinis de supervision</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {WORKFORCE_PRESETS.map((p) => (
                <button
                  key={p.name}
                  type="button"
                  className="preset-btn"
                  onClick={() => handleApplyPreset(p)}
                >
                  <span style={{ fontWeight: 600 }}>{p.name}</span>
                  <span style={{ fontSize: 11, color: 'var(--muted)' }}>{p.desc}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Sliders */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <label className="field-label" style={{ margin: 0 }}>Score Qualité Global de la session</label>
                <b style={{ color: score < 75 ? '#be123c' : '#0d9488' }}>{score} / 100</b>
              </div>
              <input
                type="range"
                min="30"
                max="100"
                value={score}
                onChange={(e) => setScore(Number(e.target.value))}
                style={{ width: '100%' }}
              />
              <div style={{ fontSize: 11, color: 'var(--muted)', display: 'flex', justifyContent: 'space-between' }}>
                <span>Seuil critique (&lt;75)</span>
                <span>Seuil cible (75+)</span>
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <label className="field-label" style={{ margin: 0 }}>Score d'Empathie perçu</label>
                <b style={{ color: empathie < 75 ? '#b45309' : '#0d9488' }}>{empathie} / 100</b>
              </div>
              <input
                type="range"
                min="30"
                max="100"
                value={empathie}
                onChange={(e) => setEmpathie(Number(e.target.value))}
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <label className="field-label" style={{ margin: 0 }}>Score d'Ancrage documentaire</label>
                <b style={{ color: groundedness == null ? 'var(--muted)' : groundedness < 75 ? '#b45309' : '#0d9488' }}>
                  {groundedness == null ? 'Non vérifié' : `${groundedness} / 100`}
                </b>
              </div>
              <input
                type="range"
                min="30"
                max="100"
                value={groundedness ?? 65}
                onChange={(e) => setGroundedness(Number(e.target.value))}
                style={{ width: '100%' }}
              />
            </div>
          </div>

          {/* Real-time KPI Context */}
          {kpi && (
            <div className="panel" style={{ background: '#fafafb', padding: 10 }}>
              <span className="field-label" style={{ marginBottom: 6 }}>Contexte KPI en temps réel</span>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 12 }}>
                <div>Taux d'escalade : <strong>{fmt(kpi.tauxEscalade, '%')}</strong></div>
                <div>Qualité moyenne : <strong>{fmt(kpi.qualiteReponses, '%')}</strong></div>
                <div>Résolution autonome : <strong>{fmt(kpi.tauxResolution, '%')}</strong></div>
                <div>Temps moyen : <strong>{fmt(kpi.tempsTraitementSec, 's')}</strong></div>
              </div>
            </div>
          )}

          {error && (
            <div className="error-box">
              <AlertTriangle size={16} /> {error}
            </div>
          )}

          <div style={{ marginTop: 'auto' }}>
            <button
              className="btn-primary"
              style={{ width: '100%', background: '#b45309' }}
              onClick={handleRunDecisions}
              disabled={loading}
            >
              {loading ? (
                <>
                  <RefreshCw size={16} className="spin" /> Analyse des règles opérationnelles…
                </>
              ) : (
                <>
                  <Users size={16} /> Déclencher les décisions managériales
                </>
              )}
            </button>
          </div>
        </div>

        {/* Results Column */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <h5>
            <ShieldAlert size={16} color="#b45309" /> Résultat · Plan d'Actions Managériales & Supervision
          </h5>

          {!result && !loading && (
            <div className="empty-state">
              <div className="empty-state-icon" style={{ background: '#fef3c7', color: '#b45309' }}>
                <Users size={32} />
              </div>
              <h4>Aucune analyse managériale déclenchée</h4>
              <p>
                Réglez les curseurs d'évaluation ou choisissez un scénario préconfiguré, puis cliquez sur « Déclencher les décisions managériales ».
              </p>
            </div>
          )}

          {loading && (
            <div className="empty-state">
              <div className="orb busy" style={{ width: 70, height: 70 }} />
              <p style={{ color: 'var(--muted)', marginTop: 12 }}>
                Évaluation des règles métier, calcul de charge et arbitrage des actions…
              </p>
            </div>
          )}

          {result && !loading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Status Header */}
              <div
                className="score-summary-card"
                style={{
                  background: result.status === 'OPTIMAL' ? '#f0fdf4' : '#fff1f2',
                  borderColor: result.status === 'OPTIMAL' ? '#86efac' : '#fecdd3',
                }}
              >
                <div>
                  <div style={{ fontSize: 12, color: 'var(--muted)' }}>Statut opérationnel de la session</div>
                  <h4 style={{ margin: '2px 0 0', color: result.status === 'OPTIMAL' ? '#15803d' : '#be123c' }}>
                    {result.status === 'OPTIMAL' ? '✅ Session Optimale' : '⚠️ Intervention Managériale Requise'}
                  </h4>
                </div>
                <span
                  className="score-badge"
                  style={{
                    background: result.status === 'OPTIMAL' ? '#dcfce7' : '#ffe4e6',
                    color: result.status === 'OPTIMAL' ? '#15803d' : '#be123c',
                  }}
                >
                  Score {result.auditScore}/100
                </span>
              </div>

              {/* Detected Problems */}
              <div>
                <span className="field-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <AlertTriangle size={14} color="#be123c" /> Problèmes & Alertes identifiés ({result.problems.length}) :
                </span>
                {result.problems.length === 0 ? (
                  <p style={{ fontSize: 13, color: '#15803d', margin: '4px 0' }}>
                    Aucune anomalie critique détectée. Tous les critères dépassent le seuil d'intervention.
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6 }}>
                    {result.problems.map((p) => (
                      <div key={p} className="alert-item">
                        <AlertTriangle size={15} color="#be123c" />
                        <span>{p}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Action Plan */}
              <div>
                <span className="field-label">Plan d'actions correctives & managériales ({result.actions.length}) :</span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 6 }}>
                  {result.actions.map((a, idx) => {
                    const pm = PRIO_META[a.priority] || PRIO_META.basse
                    return (
                      <div key={idx} className="action-card">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                          <span style={{ fontWeight: 600, fontSize: 13, textTransform: 'uppercase', letterSpacing: '.03em', color: '#334155' }}>
                            Type : {a.type.replace('_', ' ')}
                          </span>
                          <span className="prio" style={{ background: pm.bg, color: pm.color }}>
                            {pm.icon} {pm.label}
                          </span>
                        </div>
                        <p style={{ margin: '0 0 6px', fontSize: 13, color: 'var(--text)' }}>{a.description}</p>
                        <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                          Attribué à : <strong>{a.responsible}</strong>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Operational Summary */}
              <div className="panel" style={{ background: '#f8fafc', padding: 12 }}>
                <h6 style={{ margin: '0 0 8px', fontSize: 12 }}>Synthèse d'impact opérationnel :</h6>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 12 }}>
                  <div>Impact Staffing : <strong>{result.workforceSummary.staffingImpact}</strong></div>
                  <div>Formation suggérée : <strong>{result.workforceSummary.trainingModuleSuggested}</strong></div>
                  <div>Mise à jour Base de connaissances : <strong>{result.workforceSummary.kbUpdateRequired ? 'Oui' : 'Non requise'}</strong></div>
                </div>
              </div>

              {/* Loop back to global simulation */}
              <div className="handoff-box" style={{ borderColor: 'rgba(139, 92, 246, 0.4)', background: '#faf8ff' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 34, height: 34, borderRadius: 8, background: '#ede9fe', color: '#7c3aed', display: 'grid', placeItems: 'center' }}>
                    <Sparkles size={18} />
                  </div>
                  <div>
                    <h5 style={{ margin: 0, fontSize: 13, color: '#6d28d9' }}>Boucle d'optimisation terminée</h5>
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--muted)' }}>
                      Toutes les données et décisions ont été consignées dans le jumeau numérique.
                    </p>
                  </div>
                </div>
                <button
                  className="btn-primary"
                  style={{ background: '#7c3aed', marginTop: 10, width: '100%' }}
                  onClick={() => navigate('/')}
                >
                  Revenir à la Simulation Globale <ArrowRight size={15} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
