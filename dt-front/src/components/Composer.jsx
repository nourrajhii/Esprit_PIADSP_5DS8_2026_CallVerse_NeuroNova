import { useRef, useState } from 'react'
import { BookOpen, ImagePlus, Lightbulb, ArrowUp, Sparkles, Paperclip, X, MessageSquare } from 'lucide-react'
import { PROFILES } from '../api/mock'

const SCENARIO_SUGGESTIONS = [
  { label: "😤 Facture anormalement élevée", text: "Ma facture de ce mois est bien plus élevée que d'habitude, je veux une explication." },
  { label: "⏳ Remboursement en attente", text: "Je n'ai toujours pas reçu mon remboursement demandé il y a 5 jours." },
  { label: "🔐 SMS suspect reçu", text: "J'ai reçu un SMS bizarre au nom de votre banque, est-ce un phishing ?" },
  { label: "💳 Carte bloquée à l'étranger", text: "Ma carte est bloquée alors que je suis en voyage à l'étranger, c'est urgent." },
  { label: "📉 Prélèvement non autorisé", text: "Un prélèvement que je ne reconnais pas vient de passer sur mon compte." },
]

export default function Composer({ onSend, loading, profile, setProfile, conversationMode, setConversationMode, messageCount, setMessageCount }) {
  const [text, setText] = useState('')
  const [rag, setRag] = useState(true)
  const [imagePreview, setImagePreview] = useState(null)
  const [imageFile, setImageFile] = useState(null)
  const [showSuggestions, setShowSuggestions] = useState(false)

  const fileInputRef = useRef(null)
  const suggestionsRef = useRef(null)

  const submit = () => {
    if (loading) return
    onSend({
      profile,
      message: text.trim() || undefined,
      rag,
      image: imageFile || undefined,
      conversationMode,
      messageCount: conversationMode ? messageCount : 1,
    })
    setText('')
    setImagePreview(null)
    setImageFile(null)
    setShowSuggestions(false)
  }

  const handleImageChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImageFile(file)
    const reader = new FileReader()
    reader.onload = (ev) => setImagePreview(ev.target.result)
    reader.readAsDataURL(file)
    e.target.value = ''
  }

  const removeImage = () => {
    setImagePreview(null)
    setImageFile(null)
  }

  const pickSuggestion = (suggText) => {
    setText(suggText)
    setShowSuggestions(false)
  }

  return (
    <div className="composer-wrap" style={{ position: 'relative' }}>
      {/* Suggestions dropdown */}
      {showSuggestions && (
        <div className="suggestions-dropdown" ref={suggestionsRef}>
          <p className="suggestions-title">💡 Idées de scénarios</p>
          {SCENARIO_SUGGESTIONS.map((s) => (
            <button key={s.label} className="suggestion-item" onClick={() => pickSuggestion(s.text)}>
              <span className="suggestion-label">{s.label}</span>
              <span className="suggestion-text">{s.text}</span>
            </button>
          ))}
        </div>
      )}

      <div className="composer">
        {/* Image preview */}
        {imagePreview && (
          <div className="image-preview-wrap">
            <img src={imagePreview} alt="Aperçu" className="image-preview" />
            <button className="image-remove" onClick={removeImage} title="Supprimer l'image">
              <X size={12} />
            </button>
          </div>
        )}

        <textarea
          rows={2}
          value={text}
          placeholder="Écrivez la demande du client… (vide = générée par le Client Simulator Agent)"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
        />
        <div className="composer-row">
          <div className="tools">
            <button className={`chip ${rag ? 'active' : ''}`} onClick={() => setRag(!rag)} title="Consulter les procédures et fiches internes">
              <BookOpen size={15} /> Base documentaire
            </button>

            {/* Image button */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              style={{ display: 'none' }}
              onChange={handleImageChange}
            />
            <button
              className={`chip ${imagePreview ? 'active' : ''}`}
              title="Joindre une image"
              onClick={() => fileInputRef.current?.click()}
            >
              <ImagePlus size={16} />
            </button>

            {/* Lightbulb button */}
            <button
              className={`chip ${showSuggestions ? 'active' : ''}`}
              title="Idées de scénarios"
              onClick={() => setShowSuggestions((v) => !v)}
            >
              <Lightbulb size={16} />
            </button>
          </div>

          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button className="send" onClick={submit} disabled={loading} title="Lancer la simulation">
              <ArrowUp size={17} />
            </button>
          </div>
        </div>
      </div>
      <div className="composer-foot">
        <div className="left">
          <Sparkles size={16} color="#a78bfa" /> Profil client
          <select className="small-btn" value={profile} onChange={(e) => setProfile(e.target.value)}>
            {PROFILES.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
        </div>
        <div className="conv-controls">
          <button
            className={`conv-toggle ${conversationMode ? 'active' : ''}`}
            onClick={() => setConversationMode(!conversationMode)}
            title={conversationMode ? 'Désactiver le mode conversation' : 'Activer le mode conversation'}
          >
            <MessageSquare size={14} />
            Conversation
          </button>
          {conversationMode && (
            <div className="msg-count-picker">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  className={`msg-count-dot ${messageCount === n ? 'active' : ''}`}
                  onClick={() => setMessageCount(n)}
                  title={`${n} message${n > 1 ? 's' : ''}`}
                >
                  {n}
                </button>
              ))}
              <span className="msg-count-label">{messageCount} msg</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

