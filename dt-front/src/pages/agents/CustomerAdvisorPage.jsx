import { useState, useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Bot, Sparkles, BookOpen, ArrowRight, RefreshCw, Sliders, CheckCircle2, AlertCircle, MessageSquare, Plus, Trash2, UserCheck } from 'lucide-react'
import { api } from '../../api/client'
import { PROFILES, TOPICS, KB_DOCUMENTS } from '../../api/mock'
import { PROFILE_COLORS, PROFILE_SYMBOLS, PROFILE_LABELS } from '../../utils'

export default function CustomerAdvisorPage() {
  const location = useLocation()
  const navigate = useNavigate()

  const prefilled = location.state?.prefilledRequest
  // Session conversation venant du Client Simulator : une question à la fois, on y retourne après chaque réponse
  const session = location.state?.session
  const turnNumber = session ? session.history.length + 1 : 0
  const autoStarted = useRef(false)

  const [profile, setProfile] = useState(prefilled?.profile || 'mecontent')
  const [topic, setTopic] = useState(prefilled?.topic || 'facturation')
  const [message, setMessage] = useState(prefilled?.message || 'Je voudrais comprendre pourquoi ma facture est plus élevée ce mois-ci ?')
  const [conversationMessages, setConversationMessages] = useState(
    prefilled?.conversationMessages || (prefilled?.message ? [prefilled.message] : null)
  )
  const [isConversation, setIsConversation] = useState(
    prefilled?.isConversation || Boolean(prefilled?.conversationMessages && prefilled.conversationMessages.length > 1) || false
  )
  const [rag, setRag] = useState(true)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [kbDocs, setKbDocs] = useState(KB_DOCUMENTS)

  useEffect(() => {
    api.getKbDocuments().then(setKbDocs).catch(() => {})
  }, [])

  // If user navigated with new prefilled request, update form
  useEffect(() => {
    if (prefilled) {
      if (prefilled.profile) setProfile(prefilled.profile)
      if (prefilled.topic) setTopic(prefilled.topic)
      if (prefilled.message) setMessage(prefilled.message)
      if (prefilled.conversationMessages && prefilled.conversationMessages.length > 0) {
        setConversationMessages(prefilled.conversationMessages)
        setIsConversation(prefilled.isConversation ?? prefilled.conversationMessages.length > 1)
      }
    }
  }, [prefilled])

  const handleMessageChange = (idx, val) => {
    const next = [...(conversationMessages || [message])]
    next[idx] = val
    setConversationMessages(next)
    if (idx === 0) setMessage(val)
  }

  const handleAddTurn = () => {
    const current = conversationMessages || [message]
    if (current.length >= 5) return
    const newMessages = [
      ...current,
      profile === 'mecontent'
        ? "Je ne suis toujours pas satisfait, que proposez-vous de concret ?"
        : profile === 'heureux'
        ? "Merci beaucoup, pouvez-vous me confirmer que l'offre est bien activée ?"
        : "Pouvez-vous m'apporter plus de précisions sur ce point ?"
    ]
    setConversationMessages(newMessages)
    setIsConversation(true)
  }

  const handleRemoveTurn = (idx) => {
    const current = conversationMessages || [message]
    if (current.length <= 1) return
    const next = current.filter((_, i) => i !== idx)
    setConversationMessages(next)
    setMessage(next[0])
    if (next.length === 1) setIsConversation(false)
  }

  const handleGenerate = async () => {
    setLoading(true)
    setError(null)
    try {
      const activeMsgs = isConversation && conversationMessages && conversationMessages.length > 0
        ? conversationMessages
        : [message]

      const data = await api.runCustomerAdvisor({
        profile,
        message: activeMsgs[0],
        topic,
        rag,
        conversationMessages: isConversation ? activeMsgs : undefined,
        isConversation,
        messageCount: activeMsgs.length,
        turnOffset: session ? session.history.length : 0,
        // conversation page par page : le conseiller RAG a besoin des échanges précédents et de l'id de conversation
        history: session
          ? session.history.flatMap((h) => [
              { role: 'client', content: h.clientMessage },
              { role: 'advisor', content: h.advisorAnswer },
            ])
          : undefined,
        conversationId: session?.backendConvId || undefined,
      })
      setResult(data)
    } catch (e) {
      setError(e.message || 'Erreur lors de la génération de la réponse')
    } finally {
      setLoading(false)
    }
  }

  // Arrivée depuis le Simulateur : formuler directement la réponse à la question reçue
  useEffect(() => {
    if (session && !autoStarted.current) {
      autoStarted.current = true
      handleGenerate()
    }
  }, [])

  const handleReturnToSimulator = async () => {
    if (!result) return
    const history = [...session.history, { clientMessage: message, advisorAnswer: result.answer }]
    if (history.length >= session.messageCount) {
      // Conversation terminée : l'enregistrer dans l'historique avant l'analyse qualité
      try {
        await api.saveConversation({ id: session.convId, conversationId: session.backendConvId || undefined, profile, topic, rag, turns: history })
      } catch (e) {
        setError(e.message || "Impossible d'enregistrer la conversation dans l'historique")
        return
      }
      navigate('/agents/quality-analyst', {
        state: {
          prefilledContext: {
            request: { profile, message: history[0].clientMessage, topic, conversationMessages: history.map((h) => h.clientMessage) },
            response: {
              answer: result.answer,
              sources: result.sources,
              conversationExchanges: history.map((h, i) => ({ turn: i + 1, ...h, sources: [], latencyMs: 0 })),
            },
          },
        },
      })
      return
    }
    navigate('/agents/client-simulator', { state: { session: { ...session, pending: undefined, history } } })
  }

  const handleTransferToQuality = () => {
    if (!result) return
    navigate('/agents/quality-analyst', {
      state: {
        prefilledContext: {
          request: {
            profile,
            message: conversationMessages?.[0] || message,
            topic,
            intent: result.intent,
            conversationMessages: result.isConversation ? conversationMessages : undefined,
          },
          response: {
            answer: result.answer,
            intent: result.intent,
            sources: result.sources,
            latencyMs: result.latencyMs,
            conversationExchanges: result.conversationExchanges,
          },
        },
      },
    })
  }

  const currentMsgs = (isConversation && conversationMessages && conversationMessages.length > 0)
    ? conversationMessages
    : [message]

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* Banner */}
      <div className="agent-banner" style={{ borderColor: 'rgba(139, 92, 246, 0.3)' }}>
        <div className="agent-badge-icon" style={{ background: '#f5f3ff', color: '#7c3aed' }}>
          <Bot size={26} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span className="agent-step-tag" style={{ background: '#f5f3ff', color: '#6d28d9' }}>
              Agent 2 sur 4 · Réponse & Conseil
            </span>
          </div>
          <h1 className="agent-title">Agent Conseiller Client</h1>
          <p className="agent-desc">
            Consulte la documentation et les procédures de l'entreprise, formule les réponses du conseiller pour chaque message de la session client.
          </p>
        </div>
      </div>

      {prefilled && (
        <div className="injected-alert">
          <CheckCircle2 size={16} color="#7c3aed" />
          <span>
            Demande client transmise depuis l'agent <strong>Client Simulator</strong>
            {session && <strong> · Tour {turnNumber}/{session.messageCount}</strong>}
            {prefilled.conversationMessages?.length > 1 && (
              <strong> · Session de {prefilled.conversationMessages.length} messages</strong>
            )}.
          </span>
        </div>
      )}

      <div className="agent-grid">
        {/* Controls Column */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <h5>
            <Sliders size={16} color="#7c3aed" /> Paramètres d'entrée du conseiller
          </h5>

          {/* Profile & Topic row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div>
              <label className="field-label">Profil client</label>
              <select
                className="styled-select"
                value={profile}
                onChange={(e) => setProfile(e.target.value)}
              >
                {PROFILES.map((p) => (
                  <option key={p.id} value={p.id}>
                    {PROFILE_SYMBOLS[p.id]} {p.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="field-label">Thématique</label>
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
          </div>

          {/* Format mode selector */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="field-label" style={{ margin: 0 }}>Format de session</span>
            <button
              type="button"
              className={`conv-toggle ${isConversation ? 'active' : ''}`}
              onClick={() => {
                if (!isConversation && (!conversationMessages || conversationMessages.length <= 1)) {
                  setConversationMessages([message, profile === 'mecontent' ? "Je ne suis pas convaincu par votre réponse." : "Merci, pouvez-vous me confirmer ?"])
                }
                setIsConversation(!isConversation)
              }}
              style={{ padding: '3px 9px', fontSize: 12 }}
            >
              <MessageSquare size={13} />
              {isConversation ? `Conversation (${currentMsgs.length} messages)` : 'Message unique'}
            </button>
          </div>

          {/* Client Messages: multi-turn list or single textarea */}
          {isConversation ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label className="field-label" style={{ margin: 0 }}>
                  Messages de la session client ({currentMsgs.length}/5) :
                </label>
                {currentMsgs.length < 5 && (
                  <button
                    type="button"
                    onClick={handleAddTurn}
                    className="chip"
                    style={{ fontSize: 11, padding: '2px 8px' }}
                    title="Ajouter un échange dans la session (max 5)"
                  >
                    <Plus size={12} /> Ajouter un tour
                  </button>
                )}
              </div>

              {currentMsgs.map((msgText, idx) => (
                <div key={idx} style={{ background: 'var(--panel-alt, #f8fafc)', border: '1px solid #e2e8f0', borderRadius: 8, padding: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: PROFILE_COLORS[profile] || '#6d28d9' }}>
                      {PROFILE_SYMBOLS[profile]} Message {idx + 1}/{currentMsgs.length} ({idx === 0 ? 'Demande initiale' : `Relance ${idx}`})
                    </span>
                    {currentMsgs.length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveTurn(idx)}
                        style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#94a3b8' }}
                        title="Supprimer ce message"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>
                  <textarea
                    rows={2}
                    className="styled-textarea"
                    style={{ fontSize: 13, padding: '6px 8px' }}
                    value={msgText}
                    onChange={(e) => handleMessageChange(idx, e.target.value)}
                  />
                </div>
              ))}
            </div>
          ) : (
            <div>
              <label className="field-label">Demande client à traiter</label>
              <textarea
                rows={3}
                className="styled-textarea"
                placeholder="Saisissez la question du client..."
                value={message}
                onChange={(e) => {
                  setMessage(e.target.value)
                  if (conversationMessages && conversationMessages.length > 0) {
                    const next = [...conversationMessages]
                    next[0] = e.target.value
                    setConversationMessages(next)
                  }
                }}
              />
            </div>
          )}

          {/* Base documentaire Switch */}
          <div className="rag-toggle-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <BookOpen size={20} color={rag ? '#7c3aed' : 'var(--muted)'} />
              <div>
                <strong>Consultation de la Base Documentaire (RAG)</strong>
                <p style={{ margin: 0, fontSize: 11, color: 'var(--muted)' }}>
                  Interroge les fiches pratiques pour étayer les réponses du conseiller.
                </p>
              </div>
            </div>
            <button
              type="button"
              className={`chip ${rag ? 'active' : ''}`}
              onClick={() => setRag(!rag)}
              style={{ fontWeight: 600 }}
            >
              {rag ? 'Activée' : 'Désactivée'}
            </button>
          </div>

          {/* KB Document Inspector */}
          <div>
            <label className="field-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <BookOpen size={14} /> Fiches et procédures disponibles ({kbDocs.length})
            </label>
            <div className="kb-scroll-list">
              {kbDocs.map((doc) => (
                <div key={doc.id} className="kb-item">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span className="kb-item-title">{doc.title}</span>
                    <span className="source-tag">{doc.category}</span>
                  </div>
                  <p className="kb-item-excerpt">{doc.excerpt}</p>
                </div>
              ))}
            </div>
          </div>

          {error && (
            <div className="error-box">
              <AlertCircle size={16} /> {error}
            </div>
          )}

          <div style={{ marginTop: 'auto' }}>
            <button
              className="btn-primary"
              style={{ width: '100%', background: '#7c3aed' }}
              onClick={handleGenerate}
              disabled={loading}
            >
              {loading ? (
                <>
                  <RefreshCw size={16} className="spin" /> Traitement des {currentMsgs.length} messages…
                </>
              ) : (
                <>
                  <Sparkles size={16} /> Formuler les réponses du Conseiller ({currentMsgs.length} msg)
                </>
              )}
            </button>
          </div>
        </div>

        {/* Output Column */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <h5>
            <Bot size={16} color="#7c3aed" /> Résultat · Réponses formulées par le Conseiller
          </h5>

          {!result && !loading && (
            <div className="empty-state">
              <div className="empty-state-icon" style={{ background: '#f5f3ff', color: '#7c3aed' }}>
                <Bot size={32} />
              </div>
              <h4>Aucune réponse formulée</h4>
              <p>
                Cliquez sur « Formuler les réponses du Conseiller » pour traiter les {currentMsgs.length} message(s) de la session.
              </p>
            </div>
          )}

          {loading && (
            <div className="empty-state">
              <div className="orb busy" style={{ width: 70, height: 70 }} />
              <p style={{ color: 'var(--muted)', marginTop: 12 }}>
                Consultation des procédures et formulation des réponses pour chaque tour…
              </p>
            </div>
          )}

          {result && !loading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* If multi-turn session result: display every turn (client -> advisor) */}
              {result.conversationExchanges && result.conversationExchanges.length > 1 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#faf5ff', border: '1px solid #e9d5ff', padding: '8px 12px', borderRadius: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: '#6d28d9' }}>
                      💬 Session conversationnelle traitée : {result.conversationExchanges.length} échanges
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                      Temps total : {(result.latencyMs / 1000).toFixed(1)}s
                    </span>
                  </div>

                  {result.conversationExchanges.map((ex) => (
                    <div key={ex.turn} style={{ display: 'flex', flexDirection: 'column', gap: 8, background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 12 }}>
                      {/* Tour title */}
                      <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#64748b' }}>
                        Tour {ex.turn} sur {result.conversationExchanges.length}
                      </span>

                      {/* Client query */}
                      <div className="msg client" style={{ justifyContent: 'flex-start', margin: 0 }}>
                        <div style={{ maxWidth: '100%' }}>
                          <div className="meta">
                            <span className="tag" style={{ background: PROFILE_COLORS[profile] + '22', color: PROFILE_COLORS[profile] }}>
                              {PROFILE_SYMBOLS[profile]} Client ({PROFILE_LABELS[profile]})
                            </span>
                          </div>
                          <div className="bubble" style={{ background: '#0f172a', color: '#fff', fontSize: 14 }}>
                            « {ex.clientMessage} »
                          </div>
                        </div>
                      </div>

                      {/* Advisor reply */}
                      <div className="msg advisor" style={{ margin: 0 }}>
                        <div className="avatar" style={{ background: '#7c3aed', color: '#fff' }}><Bot size={14} /></div>
                        <div style={{ flex: 1 }}>
                          <div className="meta">
                            <span style={{ color: '#7c3aed', fontWeight: 600 }}>Conseiller Client · {(ex.latencyMs / 1000).toFixed(1)}s</span>
                          </div>
                          <div className="bubble" style={{ background: '#f8fafc', border: '1px solid #e2e8f0', fontSize: 14 }}>
                            {ex.advisorAnswer}
                            {ex.sources && ex.sources.length > 0 && (
                              <div className="sources" style={{ marginTop: 8 }}>
                                {ex.sources.map((s) => (
                                  <span key={s.id} className="source" style={{ fontSize: 11 }}>
                                    <BookOpen size={10} /> {s.title} ({Math.round(s.score * 100)}%)
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                /* Single message display */
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {/* Conversation page par page : rappel des tours precedents puis question courante */}
                  {session && session.history.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 6 }}>
                      {session.history.map((h, i) => (
                        <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 6, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: 10, opacity: 0.85 }}>
                          <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#64748b' }}>
                            Tour {i + 1} sur {session.messageCount}
                          </span>
                          <div className="bubble" style={{ background: '#0f172a', color: '#fff', fontSize: 13.5 }}>« {h.clientMessage} »</div>
                          <div className="bubble" style={{ background: '#fff', border: '1px solid #e2e8f0', fontSize: 13.5 }}>{h.advisorAnswer}</div>
                        </div>
                      ))}
                      <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#7c3aed' }}>
                        Tour {turnNumber} sur {session.messageCount}
                      </span>
                      <div className="bubble" style={{ background: '#0f172a', color: '#fff', fontSize: 14 }}>« {message} »</div>
                    </div>
                  )}
                  <div className="meta" style={{ justifyContent: 'space-between' }}>
                    <span>Conseiller Virtuel Relation Client</span>
                    <span>Temps de traitement : {(result.latencyMs / 1000).toFixed(1)}s{typeof result.confidence === 'number' && ` · Confiance : ${Math.round(result.confidence * 100)}%`}</span>
                  </div>
                  <div className="bubble" style={{ background: '#f8fafc', border: '1px solid var(--border)', fontSize: 14.5 }}>
                    {result.answer}
                  </div>
                </div>
              )}

              {/* Documentation Sources Cited */}
              <div>
                <span className="field-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <BookOpen size={14} color="#7c3aed" /> Fiches et procédures internes consultées ({result.sources.length}) :
                </span>
                {result.sources.length === 0 ? (
                  <p style={{ fontSize: 12, color: 'var(--muted)', margin: '4px 0' }}>
                    Aucune fiche spécifique associée (réponse générale).
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 6 }}>
                    {result.sources.map((s) => (
                      <div key={s.id} className="source-card">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 600, fontSize: 13 }}>{s.title}</span>
                          <span className="source-badge">Concordance : {Math.round(s.score * 100)}%</span>
                        </div>
                        <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--muted)' }}>
                          Extrait de référence : « {s.snippet} »
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Next Pipeline Hand-off */}
              {session ? (
                <div className="handoff-box" style={{ borderColor: 'rgba(14, 165, 233, 0.4)', background: '#f0f9ff' }}>
                  <p style={{ margin: 0, fontSize: 12, color: 'var(--muted)' }}>
                    {turnNumber < session.messageCount
                      ? <>Réponse {turnNumber}/{session.messageCount} formulée. Retournez au <strong>Client Simulator</strong> pour générer la question suivante.</>
                      : <>Dernière réponse ({turnNumber}/{session.messageCount}) formulée. Envoyez la conversation à l'<strong>Analyste Qualité</strong>.</>}
                  </p>
                  <button
                    className="btn-primary"
                    style={{ background: turnNumber < session.messageCount ? '#0284c7' : '#0d9488', marginTop: 10, width: '100%' }}
                    onClick={handleReturnToSimulator}
                  >
                    {turnNumber < session.messageCount
                      ? <>Retour au Simulateur · question {turnNumber + 1}/{session.messageCount} <ArrowRight size={15} /></>
                      : <>Ouvrir dans Analyste Qualité <ArrowRight size={15} /></>}
                  </button>
                </div>
              ) : (
              <div className="handoff-box" style={{ borderColor: 'rgba(20, 184, 166, 0.4)', background: '#f0fdfa' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 34, height: 34, borderRadius: 8, background: '#ccfbf1', color: '#0f766e', display: 'grid', placeItems: 'center' }}>
                    <ArrowRight size={18} />
                  </div>
                  <div>
                    <h5 style={{ margin: 0, fontSize: 13, color: '#0f766e' }}>Transférer à l'agent suivant</h5>
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--muted)' }}>
                      Auditer et évaluer la qualité de cette réponse avec l'<strong>Agent Analyste Qualité</strong>.
                    </p>
                  </div>
                </div>
                <button
                  className="btn-primary"
                  style={{ background: '#0d9488', marginTop: 10, width: '100%' }}
                  onClick={handleTransferToQuality}
                >
                  Ouvrir dans Analyste Qualité <ArrowRight size={15} />
                </button>
              </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
