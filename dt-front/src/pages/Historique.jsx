import { PROFILE_COLORS, PROFILE_LABELS, scoreColor } from '../utils'

export default function Historique({ conversations, onLoadConversation }) {
  return (
    <div style={{ maxWidth: 1000, margin: '0 auto' }}>
      <h1 className="page-title">Historique des conversations</h1>
      <p className="page-sub">{conversations.length} simulations enregistrées dans le Digital Twin</p>
      <div className="panel" style={{ padding: 0, overflowX: 'auto' }}>
        <table className="table">
          <thead>
            <tr><th>Demande</th><th>Profil</th><th>Score</th><th>Date</th><th></th></tr>
          </thead>
          <tbody>
            {conversations.map((c) => (
              <tr
                key={c.id}
                style={{ cursor: 'pointer' }}
                className="hist-row"
                onClick={() => onLoadConversation(c.id)}
              >
                <td>{c.title}</td>
                <td>
                  <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span className="dot" style={{ background: PROFILE_COLORS[c.profile] }} /> {PROFILE_LABELS[c.profile]}
                  </span>
                </td>
                <td><span className="score-badge" style={scoreColor(c.score)}>{c.score}/100</span></td>
                <td style={{ color: 'var(--muted)' }}>{new Date(c.createdAt).toLocaleString('fr-FR')}</td>
                <td style={{ color: 'var(--violet-strong)', fontSize: 12, fontWeight: 500 }}>Ouvrir →</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
