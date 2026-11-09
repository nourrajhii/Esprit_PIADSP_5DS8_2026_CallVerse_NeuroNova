import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  Plus, Search, MessageSquare, LayoutDashboard, History, FileCode2, PanelLeft,
  Sparkles, X, UserCheck, Bot, BarChart3, Users, Workflow
} from 'lucide-react'
import { PROFILE_COLORS, PROFILE_SYMBOLS, groupByDate, AGENTS_NAV } from '../utils'

const MAIN_NAV = [
  { to: '/', label: 'Simulation Globale', icon: Workflow },
  { to: '/dashboard', label: 'Tableau de bord', icon: LayoutDashboard },
]

const AGENTS_MENU = [
  { to: '/agents/client-simulator', label: 'Client Simulator', icon: UserCheck, color: '#0ea5e9', step: '1' },
  { to: '/agents/customer-advisor', label: 'Conseiller Client', icon: Bot, color: '#8b5cf6', step: '2' },
  { to: '/agents/quality-analyst', label: 'Analyste Qualité', icon: BarChart3, color: '#0d9488', step: '3' },
  { to: '/agents/workforce-manager', label: 'Workforce Manager', icon: Users, color: '#d97706', step: '4' },
]

const TOOLS_NAV = [
  { to: '/historique', label: 'Historique', icon: History },
  { to: '/api-docs', label: 'API (Swagger)', icon: FileCode2 },
]

export default function Sidebar({ collapsed, onToggle, conversations, onNewChat, onLoadConversation }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')

  const filtered = query.trim()
    ? conversations.filter((c) => c.title.toLowerCase().includes(query.toLowerCase()))
    : conversations

  const groups = groupByDate(filtered)

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="brand">
        <div className="brand-left">
          <div className="logo"><Sparkles size={16} /></div>
          <span className="hide-collapsed">Twinly</span>
        </div>
        <button className="icon-btn hide-collapsed" onClick={onToggle} title="Réduire"><PanelLeft size={18} /></button>
      </div>
      {collapsed && <button className="icon-btn" onClick={onToggle} title="Ouvrir"><PanelLeft size={18} /></button>}

      <button className="btn-dark" onClick={() => { onNewChat(); navigate('/') }}>
        <Plus size={16} /> <span className="hide-collapsed">Nouvelle simulation</span>
      </button>

      <label className="search hide-collapsed">
        <Search size={16} />
        <input
          placeholder="Rechercher"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {query ? (
          <button
            onClick={() => setQuery('')}
            style={{ border: 0, background: 'transparent', padding: 0, cursor: 'pointer', display: 'flex', color: 'var(--muted)' }}
            title="Effacer"
          >
            <X size={14} />
          </button>
        ) : (
          <span className="kbd">⌘K</span>
        )}
      </label>

      <nav className="nav">
        {MAIN_NAV.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} end className={({ isActive }) => (isActive ? 'active' : '')}>
            <Icon size={17} /> <span className="hide-collapsed">{label}</span>
          </NavLink>
        ))}

        <div className="nav-section-title hide-collapsed">Interfaces Agents</div>
        {AGENTS_MENU.map(({ to, label, icon: Icon, color, step }) => (
          <NavLink key={to} to={to} className={({ isActive }) => (isActive ? 'active' : '')}>
            <span
              style={{
                width: 20,
                height: 20,
                borderRadius: 5,
                background: `${color}20`,
                color: color,
                display: 'grid',
                placeItems: 'center',
                flexShrink: 0,
              }}
            >
              <Icon size={13} />
            </span>
            <span className="hide-collapsed" style={{ flex: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>{label}</span>
              <span className="nav-step-pill">{step}</span>
            </span>
          </NavLink>
        ))}

        <div className="nav-section-title hide-collapsed">Données & API</div>
        {TOOLS_NAV.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} end className={({ isActive }) => (isActive ? 'active' : '')}>
            <Icon size={16} /> <span className="hide-collapsed">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="hide-collapsed">
        {query.trim() && filtered.length === 0 && (
          <p style={{ fontSize: 12, color: 'var(--muted)', padding: '8px 4px' }}>Aucun résultat pour « {query} »</p>
        )}
        {Object.entries(groups).map(([g, items]) =>
          items.length ? (
            <div key={g}>
              <div className="hist-group">{g}</div>
              {items.map((c) => (
                <div
                  className="hist-item"
                  key={c.id}
                  title={c.title}
                  onClick={() => onLoadConversation(c.id)}
                  style={{ cursor: 'pointer' }}
                >
                  <span
                    className="dot"
                    style={{ background: PROFILE_COLORS[c.profile] }}
                    aria-hidden="true"
                  />
                  <span aria-label={c.profile} style={{ fontSize: 10, lineHeight: 1 }}>
                    {PROFILE_SYMBOLS[c.profile]}
                  </span>
                  {c.title}
                </div>
              ))}
            </div>
          ) : null,
        )}
      </div>
    </aside>
  )
}
