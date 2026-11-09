import { ChevronDown, MoreHorizontal, Link2, Download, Sparkles } from 'lucide-react'

export default function Topbar({ onExport }) {
  return (
    <header className="topbar">
      <button className="pill">
        <span className="logo mini-logo"><Sparkles size={11} /></span>
        Digital Twin <ChevronDown size={15} />
      </button>
      <div className="top-actions">
              <button className="pill" onClick={onExport}><Download size={16} /> Exporter</button>
      </div>
    </header>
  )
}
