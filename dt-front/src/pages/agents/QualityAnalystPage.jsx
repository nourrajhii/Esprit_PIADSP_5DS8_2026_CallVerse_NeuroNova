import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { BarChart3, Star, CheckCircle2, AlertTriangle, Info, ArrowRight, RefreshCw, Sliders, ShieldCheck } from 'lucide-react'
import { api } from '../../api/client'
import { scoreColor } from '../../utils'

const CRITERIA_METAS = {
  pertinence: { label: 'Pertinence', desc: 'Adéquation directe avec la question posée' },
  exactitude: { label: 'Exactitude', desc: 'Précision technique des informations' },
  groundedness: { label: 'Ancrage documentaire', desc: 'Fidélité aux fiches et procédures officielles' },
  empathie: { label: 'Empathie', desc: 'Écoute active et considération du client' },
  clarte: { label: 'Clarté', desc: 'Simplicité de compréhension du message' },
  conformite: { label: 'Conformité', desc: 'Respect des règles légales et de sécurité' },
}

const PRESET_SCENARIOS = [
  {
    name: 'Cas Nominal · Réclamation Facture avec fiches',
    request: 'Je voudrais comprendre pourquoi ma facture est plus élevée ce mois-ci ?',
    response:
      'Bonjour, je comprends votre inquiétude. Votre facture est plus élevée en raison d’une augmentation de votre consommation de données (+3,2 Go hors forfait) et de l’application de la nouvelle grille tarifaire. Conformément à la fiche tarifaire, je peux vous accorder un geste commercial.',
    profile: 'mecontent',
  },
  {
    name: 'Cas Faible Empathie · Remboursement',
    request: 'Ça fait 3 jours que j’attends mon remboursement, c’est pour quand ?',
    response: 'Bonjour, les remboursements prennent en général du temps. Votre dossier est en cours.',
    profile: 'impatient',
  },
  {
    name: 'Cas Sécurité · Tentative Phishing SMS',
    request: 'J’ai reçu un SMS bizarre me demandant mon mot de passe bancaire, est-ce vous ?',
    response:
      'Bonjour, surtout ne cliquez sur rien ! Il s’agit d’une tentative de fraude par SMS. Nos services ne vous demanderont jamais votre code secret. Votre compte est sécurisé.',
    profile: 'nerveux',
  },
]

export default function QualityAnalystPage() {
  const location = useLocation()
  const navigate = useNavigate()

  const prefilled = location.state?.prefilledContext

  const [requestText, setRequestText] = useState(
    prefilled?.request?.message || PRESET_SCENARIOS[0].request
  )
  const [responseText, setResponseText] = useState(
    prefilled?.response?.answer || PRESET_SCENARIOS[0].response
  )
  const [profile, setProfile] = useState(prefilled?.request?.profile || 'mecontent')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (prefilled) {
      if (prefilled.request?.message) setRequestText(prefilled.request.message)
      if (prefilled.response?.answer) setResponseText(prefilled.response.answer)
      if (prefilled.request?.profile) setProfile(prefilled.request.profile)
    }
  }, [prefilled])

  // Corps commun aux routes du backend unique (/agents/quality-analyst, /quality/lora/check, /quality/judge/evaluate)
  const buildBody = () => ({
    request: { message: requestText, profile },
    response: { answer: responseText, sources: prefilled?.response?.sources || [] },
  })

  const handleEvaluate = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.runQualityAnalyst(buildBody())
      setResult(data)
    } catch (e) {
      setError(e.message || 'Erreur lors de l’audit qualité')
    } finally {
      setLoading(false)
    }
  }

  const handleApplyPreset = (preset) => {
    setRequestText(preset.request)
    setResponseText(preset.response)
    setProfile(preset.profile)
    setResult(null)
  }

  const handleTransferToWorkforce = () => {
    if (!result) return
    navigate('/agents/workforce-manager', {
      state: {
        prefilledEvaluation: {
          evaluation: result,
          request: { profile, message: requestText },
        },
      },
    })
  }

  const scoreStyle = result ? scoreColor(result.globalScore) : null
  const scoreLabel = result
    ? result.globalScore >= 80
      ? 'Excellente qualité'
      : result.globalScore >= 65
      ? 'Qualité moyenne'
      : 'Qualité critique'
    : ''

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* Banner */}
      <div className="agent-banner" style={{ borderColor: 'rgba(20, 184, 166, 0.3)' }}>
        <div className="agent-badge-icon" style={{ background: '#f0fdfa', color: '#0d9488' }}>
          <BarChart3 size={26} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span className="agent-step-tag" style={{ background: '#ccfbf1', color: '#0f766e' }}>
              Agent 3 sur 4 · Audit Qualité
            </span>
          </div>
          <h1 className="agent-title">Quality Analyst Agent</h1>
          <p className="agent-desc">
            Audite la cohérence entre la question et la réponse, note 6 dimensions de qualité et identifie points forts et faiblesses.
          </p>
        </div>
      </div>

      {prefilled && (
        <div className="injected-alert">
          <CheckCircle2 size={16} color="#0d9488" />
          <span>Contexte (requête + réponse) injecté depuis le <strong>Customer Advisor Agent</strong>.</span>
        </div>
      )}

      <div className="agent-grid">
        {/* Input Column */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <h5>
            <Sliders size={16} color="#0d9488" /> Éléments soumis à l'évaluation
          </h5>

          {/* Preset Buttons */}
          <div>
            <label className="field-label">Scénarios préconfigurés de test</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {PRESET_SCENARIOS.map((p) => (
                <button
                  key={p.name}
                  type="button"
                  className="preset-btn"
                  onClick={() => handleApplyPreset(p)}
                >
                  <span style={{ fontWeight: 600 }}>{p.name}</span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="field-label">Question / Demande du client</label>
            <textarea
              rows={2}
              className="styled-textarea"
              value={requestText}
              onChange={(e) => setRequestText(e.target.value)}
            />
          </div>

          <div>
            <label className="field-label">Réponse fournie par le Conseiller</label>
            <textarea
              rows={4}
              className="styled-textarea"
              value={responseText}
              onChange={(e) => setResponseText(e.target.value)}
            />
          </div>

          {error && (
            <div className="error-box">
              <AlertTriangle size={16} /> {error}
            </div>
          )}

          <div style={{ marginTop: 'auto' }}>
            <button
              className="btn-primary"
              style={{ width: '100%', background: '#0d9488' }}
              onClick={handleEvaluate}
              disabled={loading}
            >
              {loading ? (
                <>
                  <RefreshCw size={16} className="spin" /> Audit qualité en cours…
                </>
              ) : (
                <>
                  <BarChart3 size={16} /> Évaluer la qualité de la réponse
                </>
              )}
            </button>
          </div>
        </div>

        {/* Results Column */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <h5>
            <ShieldCheck size={16} color="#0d9488" /> Résultat · Score & Grille d'Évaluation Qualité
          </h5>

          {!result && !loading && (
            <div className="empty-state">
              <div className="empty-state-icon" style={{ background: '#f0fdfa', color: '#0d9488' }}>
                <BarChart3 size={32} />
              </div>
              <h4>Aucune évaluation effectuée</h4>
              <p>
                Renseignez la demande et la réponse à gauche, puis cliquez sur « Évaluer la qualité de la réponse ».
              </p>
            </div>
          )}

          {loading && (
            <div className="empty-state">
              <div className="orb busy" style={{ width: 70, height: 70 }} />
              <p style={{ color: 'var(--muted)', marginTop: 12 }}>
                Analyse sémantique, vérification des critères et calcul du score…
              </p>
            </div>
          )}

          {result && !loading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Score Header */}
              <div className="score-summary-card">
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <Star size={28} fill="#f59e0b" color="#f59e0b" />
                  <div>
                    <div className="score-big">
                      {result.globalScore}
                      <span> / 100</span>
                    </div>
                    <span style={{ fontSize: 12, color: 'var(--muted)' }}>Score Global de Qualité</span>
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <span className="score-badge" style={scoreStyle}>
                    {scoreLabel}
                  </span>
                  <div style={{ marginTop: 6, fontSize: 11, color: 'var(--muted)' }}>
                    Statut : {result.complianceCheck}
                  </div>
                </div>
              </div>

              {/* 6 Criteria Bars */}
              <div>
                <span className="field-label">Décomposition par critère d'évaluation :</span>
                <div style={{ marginTop: 8 }}>
                  {Object.entries(result.criteria).map(([k, v]) => v == null ? (
                    <div className="bar-row" key={k} style={{ marginBottom: 10 }}>
                      <div>
                        <strong>{CRITERIA_METAS[k]?.label || k}</strong>
                        <div style={{ fontSize: 10, color: 'var(--muted)' }}>{CRITERIA_METAS[k]?.desc}</div>
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--muted)' }}>{result.accuracyStatus || 'Non vérifié'}</div>
                      <b style={{ textAlign: 'right', fontSize: 12, color: 'var(--muted)' }}>Non vérifié</b>
                    </div>
                  ) : (
                    <div className="bar-row" key={k} style={{ marginBottom: 10 }}>
                      <div>
                        <strong>{CRITERIA_METAS[k]?.label || k}</strong>
                        <div style={{ fontSize: 10, color: 'var(--muted)' }}>{CRITERIA_METAS[k]?.desc}</div>
                      </div>
                      <div className="bar" style={{ height: 8 }}>
                        <i style={{ width: `${v}%`, background: v >= 80 ? '#0d9488' : v >= 65 ? '#f59e0b' : '#f43f5e' }} />
                      </div>
                      <b style={{ textAlign: 'right', fontSize: 13 }}>{v}/100</b>
                    </div>
                  ))}
                </div>
              </div>

              {/* Strengths & Improvements */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div className="panel" style={{ background: '#f8fafc', padding: 12 }}>
                  <h6 style={{ margin: '0 0 8px', color: '#0369a1', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <CheckCircle2 size={14} /> Points forts
                  </h6>
                  <ul className="list">
                    {result.strengths.map((s) => (
                      <li key={s}>• {s}</li>
                    ))}
                  </ul>
                </div>

                <div className="panel" style={{ background: '#f8fafc', padding: 12 }}>
                  <h6 style={{ margin: '0 0 8px', color: '#b45309', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <AlertTriangle size={14} /> Axes d'amélioration
                  </h6>
                  <ul className="list">
                    {result.improvements.map((s) => (
                      <li key={s}>• {s}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {result.alerts?.length > 0 && (
                <div className="error-box" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                  {result.alerts.map((a) => (
                    <span key={a}><AlertTriangle size={14} /> {a}</span>
                  ))}
                  {result.requiresHumanReview && <strong>Revue humaine requise.</strong>}
                </div>
              )}

              {/* Hand-off to Workforce Manager */}
              <div className="handoff-box" style={{ borderColor: 'rgba(245, 158, 11, 0.4)', background: '#fffbeb' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 34, height: 34, borderRadius: 8, background: '#fef3c7', color: '#b45309', display: 'grid', placeItems: 'center' }}>
                    <ArrowRight size={18} />
                  </div>
                  <div>
                    <h5 style={{ margin: 0, fontSize: 13, color: '#92400e' }}>Transférer à l'agent suivant</h5>
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--muted)' }}>
                      Déclencher les décisions managériales et d'optimisation avec <strong>Workforce Manager Agent</strong>.
                    </p>
                  </div>
                </div>
                <button
                  className="btn-primary"
                  style={{ background: '#d97706', marginTop: 10, width: '100%' }}
                  onClick={handleTransferToWorkforce}
                >
                  Ouvrir dans Workforce Manager <ArrowRight size={15} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
