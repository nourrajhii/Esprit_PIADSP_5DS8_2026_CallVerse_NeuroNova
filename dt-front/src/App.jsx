import { lazy, Suspense, useEffect, useState } from 'react'
import { Routes, Route, useLocation, useNavigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Topbar from './components/Topbar'
import Simulation from './pages/Simulation'
import Dashboard from './pages/Dashboard'
import Historique from './pages/Historique'
import ClientSimulatorPage from './pages/agents/ClientSimulatorPage'
import CustomerAdvisorPage from './pages/agents/CustomerAdvisorPage'
import QualityAnalystPage from './pages/agents/QualityAnalystPage'
import WorkforceManagerPage from './pages/agents/WorkforceManagerPage'
import { api } from './api/client'

const ApiDocs = lazy(() => import('./pages/ApiDocs'))

export default function App() {
  const [collapsed, setCollapsed] = useState(false)
  const [conversations, setConversations] = useState([])
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  const refresh = () => api.getConversations().then(setConversations)
  // Recharger à chaque changement de page : les conversations menées page par page s'enregistrent hors de `run`
  useEffect(() => { refresh() }, [location.pathname])

  const run = async (body) => {
    setLoading(true)
    try {
      let r
      if (body.conversationMode && body.messageCount > 1) {
        r = await api.runConversationSimulation(body)
      } else {
        r = await api.runSimulation(body)
      }
      setResults((prev) => [...prev, r])
      refresh()
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  const loadConversation = async (id) => {
    try {
      const r = await api.getSimulation(id)
      setResults([r])
      navigate('/')
    } catch (e) {
      alert(e.message)
    }
  }

  const exportChat = () => {
    const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'simulation-digital-twin.json'
    a.click()
  }

  return (
    <div className="app">
      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed(!collapsed)}
        conversations={conversations}
        onNewChat={() => setResults([])}
        onLoadConversation={loadConversation}
      />
      <main className="main">
        <Topbar onExport={exportChat} />
        <div className="main-scroll">
          <Suspense fallback={<p className="page-sub">Chargement…</p>}>
            <Routes>
              <Route path="/" element={<Simulation results={results} loading={loading} run={run} />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/agents/client-simulator" element={<ClientSimulatorPage />} />
              <Route path="/agents/customer-advisor" element={<CustomerAdvisorPage />} />
              <Route path="/agents/quality-analyst" element={<QualityAnalystPage />} />
              <Route path="/agents/workforce-manager" element={<WorkforceManagerPage />} />
              <Route path="/historique" element={<Historique conversations={conversations} onLoadConversation={loadConversation} />} />
              <Route path="/api-docs" element={<ApiDocs />} />
            </Routes>
          </Suspense>
        </div>
      </main>
    </div>
  )
}
