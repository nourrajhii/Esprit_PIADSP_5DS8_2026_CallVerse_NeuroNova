import { useEffect, useRef, useState } from 'react'
import { Receipt, Timer, ShieldAlert, Smile } from 'lucide-react'
import Composer from '../components/Composer'
import SimulationResult from '../components/SimulationResult'

const SUGGESTIONS = [
  { icon: Receipt, title: 'Client mécontent', text: 'Facture plus élevée que d\u2019habitude ce mois-ci.', profile: 'mecontent' },
  { icon: Smile, title: 'Client heureux', text: 'Très satisfait de vos services, curieux des nouveautés.', profile: 'heureux' },
  { icon: Timer, title: 'Client impatient', text: 'Remboursement en attente depuis plusieurs jours.', profile: 'impatient' },
  { icon: ShieldAlert, title: 'Client nerveux', text: 'SMS suspect reçu au sujet de son compte.', profile: 'nerveux' },
]
const STEPS = ['Client Simulator', 'Conseiller Client', 'Quality Analyst', 'Workforce Manager']

export default function Simulation({ results, loading, run, userName  }) {
  const [profile, setProfile] = useState('mecontent')
  const [conversationMode, setConversationMode] = useState(false)
  const [messageCount, setMessageCount] = useState(3)
  const [step, setStep] = useState(0)
  const endRef = useRef(null)

  useEffect(() => {
    if (!loading) return
    setStep(0)
    const t = setInterval(() => setStep((s) => Math.min(s + 1, 3)), 350)
    return () => clearInterval(t)
  }, [loading])

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [results, loading])

  const empty = results.length === 0 && !loading

  if (empty) {
    return (
      <>
        <div className="hero">
          <div className="orb" />
          <p className="hello">Bonjour</p>
          <h2>Quel scénario voulez-vous simuler ?</h2>
        </div>
        <Composer
          onSend={run}
          loading={loading}
          profile={profile}
          setProfile={setProfile}
          conversationMode={conversationMode}
          setConversationMode={setConversationMode}
          messageCount={messageCount}
          setMessageCount={setMessageCount}
        />
        <div className="cards">
          {SUGGESTIONS.map(({ icon: Icon, title, text, profile: p }) => (
            <button key={title} className="card" onClick={() => run({ profile: p, conversationMode, messageCount: conversationMode ? messageCount : 1 })}>
              <Icon size={20} strokeWidth={1.6} />
              <h4>{title}</h4>
              <p>{text}</p>
            </button>
          ))}
        </div>
      </>
    )
  }

  return (
    <>
      <div className="thread">
        {results.map((r) => <SimulationResult key={r.id} data={r} />)}
        {loading && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: 20 }}>
            <div className="orb busy" style={{ width: 60, height: 60, marginBottom: 0 }} />
            <div className="steps">
              {STEPS.map((s, i) => <span key={s} className={`step ${i <= step ? 'on' : ''}`}>{i + 1}. {s}</span>)}
            </div>
            <div className="typing"><i /><i /><i /></div>
          </div>
        )}
        <div ref={endRef} />
      </div>
      <div className="sticky-composer">
        <Composer
          onSend={run}
          loading={loading}
          profile={profile}
          setProfile={setProfile}
          conversationMode={conversationMode}
          setConversationMode={setConversationMode}
          messageCount={messageCount}
          setMessageCount={setMessageCount}
        />
      </div>
    </>
  )
}
