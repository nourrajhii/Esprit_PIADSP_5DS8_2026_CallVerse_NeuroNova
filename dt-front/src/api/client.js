import { mock } from './mock'

const BASE = import.meta.env.VITE_API_URL || '/api'
const USE_MOCK = (import.meta.env.VITE_USE_MOCK ?? 'true') === 'true'

async function http(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.message || `Erreur ${res.status}`)
  }
  return res.json()
}

// Chaque fonction correspond à un endpoint du swagger (swagger/openapi.yaml)
export const api = {
  getProfiles: () => (USE_MOCK ? mock.getProfiles() : http('/profiles')),
  getKbDocuments: () => (USE_MOCK ? mock.getKbDocuments() : http('/knowledge-base/documents')),
  getConversations: () => (USE_MOCK ? mock.getConversations() : http('/conversations')),
  getKpi: () => (USE_MOCK ? mock.getKpi() : http('/kpi')),
  runSimulation: (body) =>
    USE_MOCK ? mock.runSimulation(body) : http('/simulations', { method: 'POST', body: JSON.stringify(body) }),
  getSimulation: (id) => (USE_MOCK ? mock.getSimulation(id) : http(`/simulations/${id}`)),

  // Endpoints unitaires par agent (conforme OpenAPI)
  runClientSimulator: (body) =>
    USE_MOCK ? mock.runClientSimulator(body) : http('/agents/client-simulator', { method: 'POST', body: JSON.stringify(body) }),
  runCustomerAdvisor: (body) =>
    USE_MOCK ? mock.runCustomerAdvisor(body) : http('/agents/customer-advisor', { method: 'POST', body: JSON.stringify(body) }),
  runQualityAnalyst: (body) =>
    USE_MOCK ? mock.runQualityAnalyst(body) : http('/agents/quality-analyst', { method: 'POST', body: JSON.stringify(body) }),
  // Analyste Qualité : routes annexes du backend unique (/api/quality/*)
  getQualityHealth: () => (USE_MOCK ? mock.getQualityHealth() : http('/quality/health')),
  getLoraExperiment: () => (USE_MOCK ? mock.getLoraExperiment() : http('/quality/lora/experiment')),
  runLoraCheck: (body) =>
    USE_MOCK ? mock.runLoraCheck(body) : http('/quality/lora/check', { method: 'POST', body: JSON.stringify(body) }),
  runSecondJudge: (body) =>
    USE_MOCK ? mock.runSecondJudge(body) : http('/quality/judge/evaluate', { method: 'POST', body: JSON.stringify(body) }),
  runWorkforceManager: (body) =>
    USE_MOCK ? mock.runWorkforceManager(body) : http('/agents/workforce-manager', { method: 'POST', body: JSON.stringify(body) }),
  runConversationSimulation: (body) =>
    USE_MOCK ? mock.runConversationSimulation(body) : http('/simulations/conversation', { method: 'POST', body: JSON.stringify(body) }),
  // Enregistre dans l'historique une conversation menée page par page (Simulateur ↔ Conseiller)
  saveConversation: (body) =>
    USE_MOCK ? mock.saveConversation(body) : http('/simulations/conversation/save', { method: 'POST', body: JSON.stringify(body) }),

  // ── Dashboard BI (toujours réel — données PostgreSQL) ──────────────────────
  getDashboardKpis: () => http('/dashboard/kpis'),
  getDashboardCriteria: () => http('/dashboard/criteria'),
  getDashboardProfiles: () => http('/dashboard/profiles'),
  getDashboardTrends: (days = 30) => http(`/dashboard/trends?days=${days}`),
  getDashboardWorkforce: () => http('/dashboard/workforce-stats'),
  getDashboardAlerts: (limit = 10) => http(`/dashboard/alerts?limit=${limit}`),
  getDashboardConversations: (limit = 20) => http(`/dashboard/conversations?limit=${limit}`),
  getDashboardTopics: () => http('/dashboard/topics'),
  getDashboardClientDistribution: () => http('/dashboard/client-distribution'),
}

