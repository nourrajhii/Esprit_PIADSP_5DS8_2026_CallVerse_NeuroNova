// Colorblind-safe palette (distinguishable under deuteranopia, protanopia & tritanopia)
// Uses blue/amber/teal/rose/purple — avoids red-green confusion
export const PROFILE_COLORS = {
  calme:     '#0ea5e9', // sky-blue
  impatient: '#f59e0b', // amber
  nerveux:   '#8b5cf6', // violet
  mecontent: '#f43f5e', // rose (not pure red)
  fidele:    '#14b8a6', // teal
  confus:    '#6366f1', // indigo
  exigeant:  '#111114', // near-black
  heureux:   '#10b981', // emerald green
}

// Shape symbols so profiles are never identified by color alone
export const PROFILE_SYMBOLS = {
  calme: '●', impatient: '▲', nerveux: '◆', mecontent: '✕',
  fidele: '★', confus: '?', exigeant: '■', heureux: '☺',
}

export const PROFILE_LABELS = {
  calme: 'Calme', impatient: 'Impatient', nerveux: 'Nerveux', mecontent: 'Mécontent',
  fidele: 'Fidèle', confus: 'Confus', exigeant: 'Exigeant', heureux: 'Heureux',
}

// Colorblind-safe score colors: blue (good) / amber (medium) / rose (low)
// Each band also differs in lightness so they're distinguishable in greyscale
export function scoreColor(s) {
  if (s >= 80) return { background: '#e0f2fe', color: '#0369a1' }  // sky
  if (s >= 65) return { background: '#fef3c7', color: '#b45309' }  // amber
  return        { background: '#ffe4e6', color: '#be123c' }         // rose
}


export const AGENTS_NAV = [
  {
    id: 'client-simulator',
    to: '/agents/client-simulator',
    label: 'Client Simulator',
    fullName: 'Client Simulator Agent',
    badge: 'Générateur',
    color: '#0ea5e9',
    description: 'Simule les profils, émotions et requêtes des clients',
  },
  {
    id: 'customer-advisor',
    to: '/agents/customer-advisor',
    label: 'Conseiller Client',
    fullName: 'Customer Advisor Agent',
    badge: 'Base de connaissances',
    color: '#8b5cf6',
    description: 'Traite la demande en s’appuyant sur les procédures internes',
  },
  {
    id: 'quality-analyst',
    to: '/agents/quality-analyst',
    label: 'Analyste Qualité',
    fullName: 'Quality Analyst Agent',
    badge: 'Audit & Scoring',
    color: '#14b8a6',
    description: 'Évalue la réponse selon 6 critères et calcule le score',
  },
  {
    id: 'workforce-manager',
    to: '/agents/workforce-manager',
    label: 'Workforce Manager',
    fullName: 'Workforce Manager Agent',
    badge: 'Décisions RH & Ops',
    color: '#f59e0b',
    description: 'Pilote les escalades, formation et règles opérationnelles',
  },
]

export function groupByDate(items) {
  const today = new Date().toDateString()
  const yest = new Date(Date.now() - 864e5).toDateString()
  const groups = { "Aujourd'hui": [], Hier: [], '7 jours': [] }
  items.forEach((i) => {
    const d = new Date(i.createdAt).toDateString()
    if (d === today) groups["Aujourd'hui"].push(i)
    else if (d === yest) groups.Hier.push(i)
    else groups['7 jours'].push(i)
  })
  return groups
}
