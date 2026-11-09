import { Link } from 'react-router-dom'
import { CheckCircle2, AlertTriangle, Info, BarChart3, Users, Star, BookOpen, ExternalLink, UserCheck, Bot, MessageSquare } from 'lucide-react'
import { PROFILE_LABELS, scoreColor } from '../utils'

const CRITERIA_LABELS = {
  pertinence: 'Pertinence', exactitude: 'Exactitude', groundedness: 'Groundedness',
  empathie: 'Empathie', clarte: 'Clarté', conformite: 'Conformité',
}

// Colorblind-safe: icon shape + label + color (never color alone)
const PRIO_META = {
  haute:   { icon: '▲', label: 'Haute',   color: '#be123c', bg: '#ffe4e6' },
  moyenne: { icon: '◆', label: 'Moyenne', color: '#b45309', bg: '#fef3c7' },
  basse:   { icon: '●', label: 'Basse',   color: '#0369a1', bg: '#e0f2fe' },
}

function ConversationThread({ data }) {
  const { request, exchanges, evaluation, decision } = data
  const scoreStyle = scoreColor(evaluation.globalScore)
  const scoreLabel = evaluation.globalScore >= 80 ? 'Bon' : evaluation.globalScore >= 65 ? 'Moyen' : 'Faible'
  const ScoreIcon = evaluation.globalScore >= 80 ? CheckCircle2 : evaluation.globalScore >= 65 ? AlertTriangle : Info

  return (
    <>
      {/* Conversation header */}
      <div className="conv-header">
        <div className="conv-header-badge">
          <MessageSquare size={16} />
        </div>
        <div>
          <span className="conv-header-title">Conversation · {exchanges.length} échanges</span>
          <span className="conv-header-sub">Profil : {PROFILE_LABELS[request.profile]}</span>
        </div>
      </div>

      {/* All exchanges */}
      {exchanges.map((ex, idx) => (
        <div key={idx} className="conv-exchange">
          {/* Turn indicator */}
          <div className="conv-turn-indicator">
            <span className="conv-turn-num">{ex.turn}</span>
            {idx < exchanges.length - 1 && <div className="conv-turn-line" />}
          </div>

          <div className="conv-exchange-content">
            {/* Client message */}
            <div className="msg client">
              <div>
                <div className="meta" style={{ justifyContent: 'flex-end', gap: 8 }}>
                  <span className="tag">{PROFILE_LABELS[ex.client.profile]}</span>
                  {ex.client.sentiment !== 'neutre' && (
                    <span className="conv-sentiment">{ex.client.sentiment}</span>
                  )}
                  Tour {ex.turn}
                </div>
                <div className="bubble">{ex.client.message}</div>
              </div>
            </div>

            {/* Advisor response */}
            <div className="msg advisor">
              <div className="avatar" />
              <div style={{ flex: 1 }}>
                <div className="meta">
                  <span>Conseiller · {(ex.advisor.latencyMs / 1000).toFixed(1)}s</span>
                </div>
                <div className="bubble">
                  {ex.advisor.answer}
                  {ex.advisor.sources.length > 0 && (
                    <div className="sources">
                      {ex.advisor.sources.map((s) => (
                        <span key={s.id} className="source"><BookOpen size={10} /> {s.title} · {Math.round(s.score * 100)}%</span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Per-turn mini score */}
            <div className="conv-turn-score">
              <Star size={12} fill="#f5a524" color="#f5a524" />
              <span>{ex.evaluation.globalScore}/100</span>
            </div>
          </div>
        </div>
      ))}

      {/* Overall analysis */}
      <div className="analysis">
        <div className="panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h5 style={{ margin: 0 }}><BarChart3 size={16} color="#8b5cf6" /> Quality Analyst Agent · Synthèse</h5>
            <Link
              to="/agents/quality-analyst"
              state={{ prefilledContext: { request, response: data.response } }}
              style={{ fontSize: 11, color: '#0d9488', display: 'inline-flex', alignItems: 'center', gap: 3, fontWeight: 500 }}
              title="Tester dans l'interface Quality Analyst"
            >
              Interface <ExternalLink size={11} />
            </Link>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
            <Star size={22} fill="#f5a524" color="#f5a524" />
            <div className="score-big">{evaluation.globalScore}<span> / 100</span></div>
            <span className="conv-msg-count-badge">{exchanges.length} msg</span>
            <span
              className="score-badge"
              style={{ ...scoreStyle, marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}
              aria-label={`Score ${scoreLabel}`}
            >
              <ScoreIcon size={13} />
              {scoreLabel}
            </span>
          </div>
          {Object.entries(evaluation.criteria).map(([k, v]) => (
            <div className="bar-row" key={k}>
              <span>{CRITERIA_LABELS[k]}</span>
              <div className="bar" role="progressbar" aria-valuenow={v ?? undefined} aria-valuemin={0} aria-valuemax={100}>
                <i style={{ width: (v ?? 0) + '%' }} />
              </div>
              <b>{v ?? 'Non vérifié'}</b>
            </div>
          ))}
          {evaluation.alerts?.length > 0 && (
            <div className="error-box" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
              {evaluation.alerts.map((a) => <span key={a}>⚠ {a}</span>)}
              {evaluation.requiresHumanReview && <strong>Revue humaine requise.</strong>}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="panel">
            <h5>Résumé Qualité</h5>
            <ul className="list">
              {/* Shape ✔ for strengths */}
              {evaluation.strengths.map((s) => (
                <li key={s}>
                  <CheckCircle2 size={14} color="#0369a1" aria-label="Point fort" />
                  {s}
                </li>
              ))}
              {/* Shape △ for improvements */}
              {evaluation.improvements.map((s) => (
                <li key={s}>
                  <AlertTriangle size={14} color="#b45309" aria-label="Amélioration" />
                  {s}
                </li>
              ))}
              {/* Shape ℹ for recommendations */}
              {evaluation.recommendations.map((s) => (
                <li key={s}>
                  <Info size={14} color="#6366f1" aria-label="Recommandation" />
                  {s}
                </li>
              ))}
            </ul>
          </div>
          <div className="panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h5 style={{ margin: 0 }}><Users size={16} color="#8b5cf6" /> Workforce Manager Agent</h5>
              <Link
                to="/agents/workforce-manager"
                state={{ prefilledEvaluation: { evaluation, request } }}
                style={{ fontSize: 11, color: '#d97706', display: 'inline-flex', alignItems: 'center', gap: 3, fontWeight: 500 }}
                title="Tester dans l'interface Workforce Manager"
              >
                Interface <ExternalLink size={11} />
              </Link>
            </div>
            <ul className="list">
              {decision.problems.map((p) => (
                <li key={p}><AlertTriangle size={14} color="#be123c" aria-label="Problème" /> {p}</li>
              ))}
              {decision.actions.map((a) => {
                const pm = PRIO_META[a.priority] || PRIO_META.basse
                return (
                  <li key={a.type}>
                    • {a.description}
                    {/* Priority: shape icon + text label + color */}
                    <span
                      className="prio"
                      style={{ background: pm.bg, color: pm.color }}
                      title={`Priorité ${pm.label}`}
                      aria-label={`Priorité ${pm.label}`}
                    >
                      {pm.icon} {pm.label}
                    </span>
                  </li>
                )
              })}
            </ul>
          </div>
        </div>
      </div>
    </>
  )
}

export default function SimulationResult({ data }) {
  // If this is a conversation result, render the conversation thread
  if (data.isConversation && data.exchanges) {
    return <ConversationThread data={data} />
  }

  const { request, response, evaluation, decision } = data
  const scoreStyle = scoreColor(evaluation.globalScore)
  const scoreLabel = evaluation.globalScore >= 80 ? 'Bon' : evaluation.globalScore >= 65 ? 'Moyen' : 'Faible'
  // Icon shape changes with score level — never just color
  const ScoreIcon = evaluation.globalScore >= 80 ? CheckCircle2 : evaluation.globalScore >= 65 ? AlertTriangle : Info

  return (
    <>
      <div className="msg client">
        <div>
          <div className="meta" style={{ justifyContent: 'flex-end', gap: 8 }}>
            <span className="tag">{PROFILE_LABELS[request.profile]}</span> Client Simulator Agent
            <Link
              to="/agents/client-simulator"
              style={{ color: '#0ea5e9', display: 'inline-flex', alignItems: 'center', gap: 2, marginLeft: 4 }}
              title="Tester dans l'interface Client Simulator"
            >
              Interface <ExternalLink size={10} />
            </Link>
          </div>
          <div className="bubble">{request.message}</div>
        </div>
      </div>

      <div className="msg advisor">
        <div className="avatar" />
        <div style={{ flex: 1 }}>
          <div className="meta" style={{ justifyContent: 'space-between' }}>
            <span>Agent Conseiller Client · {(response.latencyMs / 1000).toFixed(1)}s</span>
            <Link
              to="/agents/customer-advisor"
              state={{ prefilledRequest: { profile: request.profile, message: request.message } }}
              style={{ color: '#8b5cf6', display: 'inline-flex', alignItems: 'center', gap: 2 }}
              title="Tester dans l'interface Conseiller Client"
            >
              Interface <ExternalLink size={10} />
            </Link>
          </div>
          <div className="bubble">
            {response.answer}
            <div className="sources">
              {response.sources.map((s) => (
                <span key={s.id} className="source"><BookOpen size={10} /> {s.title} · {Math.round(s.score * 100)}%</span>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="analysis">
        <div className="panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h5 style={{ margin: 0 }}><BarChart3 size={16} color="#8b5cf6" /> Quality Analyst Agent</h5>
            <Link
              to="/agents/quality-analyst"
              state={{ prefilledContext: { request, response } }}
              style={{ fontSize: 11, color: '#0d9488', display: 'inline-flex', alignItems: 'center', gap: 3, fontWeight: 500 }}
              title="Tester dans l'interface Quality Analyst"
            >
              Interface <ExternalLink size={11} />
            </Link>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
            <Star size={22} fill="#f5a524" color="#f5a524" />
            <div className="score-big">{evaluation.globalScore}<span> / 100</span></div>
            {/* Shape + text label + color — accessible for all color vision types */}
            <span
              className="score-badge"
              style={{ ...scoreStyle, marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}
              aria-label={`Score ${scoreLabel}`}
            >
              <ScoreIcon size={13} />
              {scoreLabel}
            </span>
          </div>
          {Object.entries(evaluation.criteria).map(([k, v]) => (
            <div className="bar-row" key={k}>
              <span>{CRITERIA_LABELS[k]}</span>
              <div className="bar" role="progressbar" aria-valuenow={v ?? undefined} aria-valuemin={0} aria-valuemax={100}>
                <i style={{ width: (v ?? 0) + '%' }} />
              </div>
              <b>{v ?? 'Non vérifié'}</b>
            </div>
          ))}
          {evaluation.alerts?.length > 0 && (
            <div className="error-box" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
              {evaluation.alerts.map((a) => <span key={a}>⚠ {a}</span>)}
              {evaluation.requiresHumanReview && <strong>Revue humaine requise.</strong>}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="panel">
            <h5>Résumé Qualité</h5>
            <ul className="list">
              {/* Shape ✔ for strengths */}
              {evaluation.strengths.map((s) => (
                <li key={s}>
                  <CheckCircle2 size={14} color="#0369a1" aria-label="Point fort" />
                  {s}
                </li>
              ))}
              {/* Shape △ for improvements */}
              {evaluation.improvements.map((s) => (
                <li key={s}>
                  <AlertTriangle size={14} color="#b45309" aria-label="Amélioration" />
                  {s}
                </li>
              ))}
              {/* Shape ℹ for recommendations */}
              {evaluation.recommendations.map((s) => (
                <li key={s}>
                  <Info size={14} color="#6366f1" aria-label="Recommandation" />
                  {s}
                </li>
              ))}
            </ul>
          </div>
          <div className="panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h5 style={{ margin: 0 }}><Users size={16} color="#8b5cf6" /> Workforce Manager Agent</h5>
              <Link
                to="/agents/workforce-manager"
                state={{ prefilledEvaluation: { evaluation, request } }}
                style={{ fontSize: 11, color: '#d97706', display: 'inline-flex', alignItems: 'center', gap: 3, fontWeight: 500 }}
                title="Tester dans l'interface Workforce Manager"
              >
                Interface <ExternalLink size={11} />
              </Link>
            </div>
            <ul className="list">
              {decision.problems.map((p) => (
                <li key={p}><AlertTriangle size={14} color="#be123c" aria-label="Problème" /> {p}</li>
              ))}
              {decision.actions.map((a) => {
                const pm = PRIO_META[a.priority] || PRIO_META.basse
                return (
                  <li key={a.type}>
                    • {a.description}
                    {/* Priority: shape icon + text label + color */}
                    <span
                      className="prio"
                      style={{ background: pm.bg, color: pm.color }}
                      title={`Priorité ${pm.label}`}
                      aria-label={`Priorité ${pm.label}`}
                    >
                      {pm.icon} {pm.label}
                    </span>
                  </li>
                )
              })}
            </ul>
          </div>
        </div>
      </div>
    </>
  )
}
