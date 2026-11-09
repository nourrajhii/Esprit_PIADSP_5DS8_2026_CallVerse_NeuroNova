import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { UserCheck, Sparkles, Send, ArrowRight, RefreshCw, Sliders, MessageCircle, AlertCircle, CheckCircle2, ShieldAlert, MessageSquare } from 'lucide-react'
import { api } from '../../api/client'
import { PROFILES, TOPICS } from '../../api/mock'
import { PROFILE_COLORS, PROFILE_SYMBOLS, PROFILE_LABELS } from '../../utils'

// Conversation : ce simulateur ne génère QU'UNE question à la fois.
// La réponse est produite dans la page Conseiller, qui renvoie ici avec `session` mise à jour.
export default function ClientSimulatorPage() {
  const navigate = useNavigate()
  const incoming = useLocation().state?.session
  const [profile, setProfile] = useState(incoming?.profile || 'mecontent')
  const [topic, setTopic] = useState(incoming?.topic || 'facturation')
  const [urgency, setUrgency] = useState(incoming?.urgency || 'haute')
  const [customPrompt, setCustomPrompt] = useState(incoming?.customPrompt || '')
  const [isConversation, setIsConversation] = useState(Boolean(incoming))
  const [messageCount, setMessageCount] = useState(incoming?.messageCount || 3)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  // Session conversation
  const [history, setHistory] = useState(incoming?.history || [])   // tours terminés [{ clientMessage, advisorAnswer }]
  const [pending, setPending] = useState(null)                        // question en attente de réponse du conseiller
  const [meta, setMeta] = useState(incoming?.meta || null)            // métadonnées de la 1re question
  const [backendConvId, setBackendConvId] = useState(incoming?.backendConvId || null) // id de conversation côté serveur (modèle réel)
  const started = useRef(false)

  const fetchQuestion = async ({ hist, p, t, u, count, prompt, cid = null }) => {
    setLoading(true)
    setError(null)
    try {
      const sim = await api.runClientSimulator({
        profile: p, topic: t, urgency: u,
        customPrompt: hist.length === 0 ? prompt : '',
        isConversation: true,
        messageCount: count,
        history: hist,
        // le vrai backend garde l'historique : il lui faut l'id et la dernière réponse du conseiller
        conversationId: cid || undefined,
        advisorMessage: hist.length > 0 ? hist[hist.length - 1].advisorAnswer : undefined,
      })
      if (sim.conversationId) setBackendConvId(sim.conversationId)
      if (hist.length === 0) setMeta(sim)
      setPending(sim.message)
    } catch (e) {
      setError(e.message || 'Erreur lors de la génération')
    } finally {
      setLoading(false)
    }
  }

  // Retour depuis le Conseiller : générer automatiquement la question suivante
  useEffect(() => {
    if (!incoming || started.current) return
    started.current = true
    if (incoming.history.length < incoming.messageCount) {
      fetchQuestion({
        hist: incoming.history, p: incoming.profile, t: incoming.topic, u: incoming.urgency,
        count: incoming.messageCount, prompt: incoming.customPrompt, cid: incoming.backendConvId,
      })
    }
  }, [])

  const conversationActive = isConversation && messageCount > 1
  const finished = conversationActive && history.length >= messageCount && !pending

  const handleGenerate = async () => {
    setResult(null)
    setHistory([])
    setPending(null)
    setMeta(null)
    setBackendConvId(null)
    if (conversationActive) {
      await fetchQuestion({ hist: [], p: profile, t: topic, u: urgency, count: messageCount, prompt: customPrompt })
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await api.runClientSimulator({
        profile,
        topic,
        urgency,
        customPrompt,
        isConversation: false,
        messageCount: 1,
      })
      setResult(data)
    } catch (e) {
      setError(e.message || 'Erreur lors de la génération')
    } finally {
      setLoading(false)
    }
  }

  const [convId] = useState(incoming?.convId || 'conv-' + Date.now())
  const session = { convId, backendConvId, profile, topic, urgency, customPrompt, messageCount, meta, history }

  const handleSendToAdvisor = () => {
    navigate('/agents/customer-advisor', {
      state: {
        session: { ...session, pending },
        prefilledRequest: { profile, topic, message: pending },
      },
    })
  }

  const handleSendConversationToQuality = () => {
    navigate('/agents/quality-analyst', {
      state: {
        prefilledContext: {
          request: { profile, message: history[0].clientMessage, topic, conversationMessages: history.map((h) => h.clientMessage) },
          response: {
            answer: history[history.length - 1].advisorAnswer,
            sources: [],
            conversationExchanges: history.map((h, i) => ({ turn: i + 1, ...h, sources: [], latencyMs: 0 })),
          },
        },
      },
    })
  }

  const handleTransferToAdvisor = () => {
    if (!result) return
    navigate('/agents/customer-advisor', {
      state: {
        prefilledRequest: {
          profile: result.profile,
          message: result.message,
          topic: result.topic,
          intent: result.intent,
          entities: result.entities,
        },
      },
    })
  }

  const selectedProfileMeta = PROFILES.find((p) => p.id === profile)

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* Agent Header Banner */}
      <div className="agent-banner" style={{ borderColor: 'rgba(14, 165, 233, 0.3)' }}>
        <div className="agent-badge-icon" style={{ background: '#e0f2fe', color: '#0284c7' }}>
          <UserCheck size={26} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span className="agent-step-tag" style={{ background: '#e0f2fe', color: '#0369a1' }}>
              Agent 1 sur 4 · Simulation Client
            </span>
          </div>
          <h1 className="agent-title">Client Simulator Agent</h1>
          <p className="agent-desc">
            Génère des personas réalistes, simule le comportement émotionnel d'un client et produit des requêtes contextuelles calibrées.
          </p>
        </div>
      </div>

      <div className="agent-grid">
        {/* Controls Column */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <h5>
            <Sliders size={16} color="#0284c7" /> Paramètres de génération
          </h5>

          {/* Profile Picker */}
          <div>
            <label className="field-label">
              Profil & Persona ({PROFILES.length} types)
            </label>
            <div className="profile-chips-grid">
              {PROFILES.map((p) => {
                const isSelected = p.id === profile
                return (
                  <button
                    key={p.id}
                    type="button"
                    className={`profile-chip ${isSelected ? 'active' : ''}`}
                    onClick={() => setProfile(p.id)}
                    style={{
                      borderColor: isSelected ? PROFILE_COLORS[p.id] : undefined,
                      background: isSelected ? 'var(--violet-soft)' : undefined,
                    }}
                  >
                    <span
                      className="dot"
                      style={{ background: PROFILE_COLORS[p.id] }}
                      aria-hidden="true"
                    />
                    <span style={{ fontSize: 11, fontWeight: 700 }} aria-hidden="true">
                      {PROFILE_SYMBOLS[p.id]}
                    </span>
                    <span>{p.label}</span>
                  </button>
                )
              })}
            </div>
            {selectedProfileMeta && (
              <p className="field-hint" style={{ marginTop: 6 }}>
                💡 Caractéristique : <em>{selectedProfileMeta.description}</em>
              </p>
            )}
          </div>

          {/* Topic Picker */}
          <div>
            <label className="field-label">Thématique & Sujet d'appel</label>
            <select
              className="styled-select"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
            >
              {TOPICS.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          {/* Urgency */}
          <div>
            <label className="field-label">Niveau d'urgence perçu</label>
            <div style={{ display: 'flex', gap: 8 }}>
              {['basse', 'moyenne', 'haute'].map((u) => (
                <button
                  key={u}
                  type="button"
                  className={`chip ${urgency === u ? 'active' : ''}`}
                  onClick={() => setUrgency(u)}
                  style={{ flex: 1, justifyContent: 'center', textTransform: 'capitalize' }}
                >
                  {u === 'haute' ? '▲ Haute' : u === 'moyenne' ? '◆ Moyenne' : '● Basse'}
                </button>
              ))}
            </div>
          </div>

          {/* Mode conversation & Nombre de messages (1 à 5) */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <label className="field-label" style={{ margin: 0 }}>
                Format de simulation
              </label>
              <button
                type="button"
                className={`conv-toggle ${isConversation ? 'active' : ''}`}
                onClick={() => setIsConversation(!isConversation)}
                style={{ padding: '3px 9px', fontSize: 12 }}
              >
                <MessageSquare size={13} />
                {isConversation ? 'Conversation (1-5 msg)' : 'Message unique'}
              </button>
            </div>
            {isConversation && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'var(--panel-alt, #f8fafc)', padding: '8px 12px', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                <span style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 500 }}>Échanges (session) :</span>
                <div className="msg-count-picker">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button
                      key={n}
                      type="button"
                      className={`msg-count-dot ${messageCount === n ? 'active' : ''}`}
                      onClick={() => setMessageCount(n)}
                      title={`${n} message${n > 1 ? 's' : ''}`}
                    >
                      {n}
                    </button>
                  ))}
                  <span className="msg-count-label">{messageCount} msg</span>
                </div>
              </div>
            )}
          </div>

          {/* Custom Prompt / Override */}
          <div>
            <label className="field-label">
              Instruction personnalisée ou question libre <small>(optionnel)</small>
            </label>
            <textarea
              rows={3}
              className="styled-textarea"
              placeholder="Laissez vide pour une génération automatique basée sur le persona et la thématique..."
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
            />
          </div>

          {error && (
            <div className="error-box">
              <AlertCircle size={16} /> {error}
            </div>
          )}

          <div style={{ display: 'flex', gap: 10, marginTop: 'auto' }}>
            <button
              className="btn-primary"
              style={{ flex: 1, background: '#0284c7' }}
              onClick={handleGenerate}
              disabled={loading}
            >
              {loading ? (
                <>
                  <RefreshCw size={16} className="spin" /> Génération en cours…
                </>
              ) : (
                <>
                  <Sparkles size={16} /> {conversationActive ? `Démarrer la conversation (${messageCount} msg)` : 'Générer la demande client'}
                </>
              )}
            </button>
          </div>
        </div>

        {/* Output Column */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <h5>
            <MessageCircle size={16} color="#0284c7" /> Résultat · Demande Client Simulée
          </h5>

          {!result && !loading && !pending && history.length === 0 && (
            <div className="empty-state">
              <div className="empty-state-icon" style={{ background: '#e0f2fe', color: '#0369a1' }}>
                <UserCheck size={32} />
              </div>
              <h4>Aucune demande générée</h4>
              <p>
                Configurez le persona client à gauche et cliquez sur « Générer la demande client » pour tester unitairement cet agent.
              </p>
            </div>
          )}

          {conversationActive && (history.length > 0 || pending) && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
              <span className="field-label">
                Conversation · tour {Math.min(history.length + (pending ? 1 : 0), messageCount)}/{messageCount} :
              </span>
              {history.map((t, idx) => (
                <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div className="msg client" style={{ justifyContent: 'flex-start' }}>
                    <div style={{ maxWidth: '100%' }}>
                      <div className="meta">
                        <span className="tag" style={{ background: PROFILE_COLORS[profile] + '22', color: PROFILE_COLORS[profile] }}>
                          {PROFILE_SYMBOLS[profile]} {PROFILE_LABELS[profile]} · Tour {idx + 1}/{messageCount}
                        </span>
                      </div>
                      <div className="bubble" style={{ background: '#0f172a', color: '#fff', fontSize: 14 }}>« {t.clientMessage} »</div>
                    </div>
                  </div>
                  <div className="msg advisor">
                    <div className="avatar" />
                    <div style={{ flex: 1 }}>
                      <div className="meta"><span>Conseiller · Tour {idx + 1}</span></div>
                      <div className="bubble">{t.advisorAnswer}</div>
                    </div>
                  </div>
                </div>
              ))}
              {pending && (
                <div className="msg client" style={{ justifyContent: 'flex-start' }}>
                  <div style={{ maxWidth: '100%' }}>
                    <div className="meta">
                      <span className="tag" style={{ background: PROFILE_COLORS[profile] + '22', color: PROFILE_COLORS[profile] }}>
                        {PROFILE_SYMBOLS[profile]} {PROFILE_LABELS[profile]} · Tour {history.length + 1}/{messageCount}
                      </span>
                    </div>
                    <div className="bubble" style={{ background: '#0f172a', color: '#fff', fontSize: 14 }}>« {pending} »</div>
                  </div>
                </div>
              )}
            </div>
          )}

          {loading && (
            <div className="empty-state">
              <div className="orb busy" style={{ width: 70, height: 70 }} />
              <p style={{ color: 'var(--muted)', marginTop: 12 }}>
                {conversationActive ? `Génération de la question ${history.length + 1}/${messageCount}…` : 'Simulation du comportement client en cours…'}
              </p>
            </div>
          )}

          {conversationActive && !loading && pending && (
            <div className="handoff-box" style={{ borderColor: 'rgba(139, 92, 246, 0.4)', background: '#faf8ff' }}>
              <p style={{ margin: 0, fontSize: 12, color: 'var(--muted)' }}>
                Question {history.length + 1}/{messageCount} générée. Envoyez-la à l'<strong>Agent Conseiller Client</strong> pour obtenir la réponse ; vous reviendrez ici pour la question suivante.
              </p>
              <button className="btn-primary" style={{ background: '#7c3aed', marginTop: 10, width: '100%' }} onClick={handleSendToAdvisor}>
                Envoyer au Conseiller Client <ArrowRight size={15} />
              </button>
            </div>
          )}

          {finished && (
            <div className="handoff-box" style={{ borderColor: 'rgba(20, 184, 166, 0.4)', background: '#f0fdfa' }}>
              <p style={{ margin: 0, fontSize: 12, color: 'var(--muted)' }}>
                Conversation terminée ({messageCount} échanges). Vous pouvez l'évaluer avec l'<strong>Agent Analyste Qualité</strong>.
              </p>
              <button className="btn-primary" style={{ background: '#0d9488', marginTop: 10, width: '100%' }} onClick={handleSendConversationToQuality}>
                Ouvrir dans Analyste Qualité <ArrowRight size={15} />
              </button>
            </div>
          )}

          {conversationActive && meta && !loading && (
            <div style={{ marginTop: 16 }}>
              <div className="meta-card-grid">
                <div className="meta-box">
                  <span className="meta-label">Motif / Intention identifiée</span>
                  <span className="meta-value" style={{ color: '#0369a1' }}>{meta.intent.replace(/_/g, ' ')}</span>
                </div>
                <div className="meta-box">
                  <span className="meta-label">Sentiment client</span>
                  <span className="meta-value" style={{ textTransform: 'capitalize' }}>{meta.sentiment.replace(/_/g, ' ')}</span>
                </div>
                <div className="meta-box">
                  <span className="meta-label">Tonalité psychologique</span>
                  <span className="meta-value">{meta.tone}</span>
                </div>
              </div>
            </div>
          )}

          {!conversationActive && result && !loading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Message Bubble Preview */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span className="field-label">Message simulé par l'agent :</span>

                {(
                  <div className="msg client" style={{ justifyContent: 'flex-start' }}>
                    <div style={{ maxWidth: '100%' }}>
                      <div className="meta">
                        <span className="tag" style={{ background: PROFILE_COLORS[result.profile] + '22', color: PROFILE_COLORS[result.profile] }}>
                          {PROFILE_SYMBOLS[result.profile]} {result.profileLabel}
                        </span>
                        <span>Urgence {result.urgency}</span>
                        <span>{new Date(result.generatedAt).toLocaleTimeString()}</span>
                      </div>
                      <div className="bubble" style={{ background: '#0f172a', color: '#fff', fontSize: 15 }}>
                        « {result.message} »
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Extracted Metadata Grid */}
              <div className="meta-card-grid">
                <div className="meta-box">
                  <span className="meta-label">Motif / Intention identifiée</span>
                  <span className="meta-value" style={{ color: '#0369a1' }}>
                    {result.intent.replace(/_/g, ' ')}
                  </span>
                </div>
                <div className="meta-box">
                  <span className="meta-label">Sentiment client</span>
                  <span className="meta-value" style={{ textTransform: 'capitalize' }}>
                    {result.sentiment.replace(/_/g, ' ')}
                  </span>
                </div>
                <div className="meta-box">
                  <span className="meta-label">Tonalité psychologique</span>
                  <span className="meta-value">{result.tone}</span>
                </div>
              </div>

              {/* Extracted Entities */}
              <div>
                <span className="field-label">Éléments contextuels identifiés :</span>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                  {Object.entries(result.entities).map(([k, v]) => (
                    <span key={k} className="entity-pill">
                      <strong>{k.replace(/_/g, ' ')}:</strong> {v}
                    </span>
                  ))}
                </div>
              </div>

              {/* Pipeline Hand-off Action */}
              <div className="handoff-box" style={{ borderColor: 'rgba(139, 92, 246, 0.4)', background: '#faf8ff' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 34, height: 34, borderRadius: 8, background: '#ede9fe', color: '#7c3aed', display: 'grid', placeItems: 'center' }}>
                    <ArrowRight size={18} />
                  </div>
                  <div>
                    <h5 style={{ margin: 0, fontSize: 13, color: '#6d28d9' }}>Transférer à l'agent suivant</h5>
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--muted)' }}>
                      Transmettre cette demande à l'<strong>Agent Conseiller Client</strong>.
                    </p>
                  </div>
                </div>
                <button
                  className="btn-primary"
                  style={{ background: '#7c3aed', marginTop: 10, width: '100%' }}
                  onClick={handleTransferToAdvisor}
                >
                  Ouvrir dans Conseiller Client <ArrowRight size={15} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
