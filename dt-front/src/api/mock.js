// Données simulées, conformes aux schémas de swagger/openapi.yaml
export const PROFILES = [
  { id: 'calme', label: 'Calme', description: 'Pose sa question posément' },
  { id: 'impatient', label: 'Impatient', description: 'Veut une réponse immédiate' },
  { id: 'nerveux', label: 'Nerveux', description: 'Inquiet, a besoin d’être rassuré' },
  { id: 'mecontent', label: 'Mécontent', description: 'Exprime une insatisfaction' },
  { id: 'fidele', label: 'Fidèle', description: 'Client de longue date' },
  { id: 'confus', label: 'Confus', description: 'Ne comprend pas bien sa situation' },
  { id: 'exigeant', label: 'Exigeant', description: 'Attend une réponse précise et complète' },
  { id: 'heureux', label: 'Heureux', description: 'Client satisfait, enthousiaste et bienveillant' },
]

export const TOPICS = [
  { id: 'facturation', label: 'Facturation & Frais', defaultMsg: 'Je voudrais comprendre pourquoi ma facture est plus élevée ce mois-ci ?' },
  { id: 'remboursement', label: 'Remboursement & Avoir', defaultMsg: 'Ça fait 3 jours que j’attends mon remboursement, c’est pour quand ?' },
  { id: 'securite', label: 'Sécurité & Alerte SMS', defaultMsg: 'J’ai reçu un SMS suspect au sujet de mon compte, est-ce une fraude ?' },
  { id: 'fidelite', label: 'Offre & Fidélité', defaultMsg: 'Je suis client depuis 10 ans, avez-vous une offre ou réduction de fidélité ?' },
  { id: 'technique', label: 'Panne & Accès aux services', defaultMsg: 'Mes services ne fonctionnent plus depuis ce matin, pouvez-vous débloquer la situation ?' },
  { id: 'resiliation', label: 'Résiliation de contrat', defaultMsg: 'Je souhaite résilier mon abonnement sans frais suite à vos changements tarifaires.' },
  { id: 'produit', label: 'Conseil produit', defaultMsg: 'Je cherche un nettoyant visage pour peau mixte, avec un budget de 40 DT maximum.' },
  { id: 'soins', label: 'Soins peau & cheveux', defaultMsg: 'J’ai la peau très sèche qui tiraille, que me conseillez-vous ?' },
  { id: 'bebe_maman', label: 'Bébé & maman', defaultMsg: 'Mon bébé a les fesses rouges à chaque change, quel produit utiliser ?' },
  { id: 'bien_etre', label: 'Bien-être & compléments', defaultMsg: 'Je suis souvent fatiguée en ce moment, avez-vous des vitamines à me conseiller ?' },
  { id: 'precautions', label: 'Précautions & orientation', defaultMsg: 'Je suis enceinte, puis-je utiliser des huiles essentielles et des compléments ?' },
  { id: 'choix', label: 'Aide au choix & rupture', defaultMsg: 'Le produit que je voulais est en rupture, avez-vous une alternative dans mon budget ?' },
  { id: 'symptome', label: 'Symptômes & orientation médicale', defaultMsg: 'J’ai mal aux dents depuis deux jours, quel médecin dois-je consulter ?' },
]

export const KB_DOCUMENTS = [
  {
    id: 'kb-12',
    title: 'Grille tarifaire et gestion des dépassements 2026',
    category: 'Facturation',
    chunks: 14,
    updatedAt: '2026-09-01T10:00:00Z',
    excerpt: 'Les dépassements de données sont facturés 0,05€/Mo. Tout dépassement fait l’objet d’une alerte SMS préventive dès 80% du forfait consommé.',
  },
  {
    id: 'kb-07',
    title: 'Procédure contestation et remise commerciale',
    category: 'Facturation',
    chunks: 8,
    updatedAt: '2026-08-15T14:30:00Z',
    excerpt: 'Le conseiller peut accorder un avoir commercial jusqu’à 30€ en cas de premier dépassement involontaire d’un client fidèle.',
  },
  {
    id: 'kb-21',
    title: 'Délais de traitement des remboursements',
    category: 'Paiement',
    chunks: 5,
    updatedAt: '2026-09-20T09:15:00Z',
    excerpt: 'Les remboursements sont validés en 48h ouvrées puis crédités sous 3 à 5 jours ouvrés selon les délais interbancaires.',
  },
  {
    id: 'kb-34',
    title: 'Guide d’authentification et sécurité contre le phishing',
    category: 'Sécurité',
    chunks: 11,
    updatedAt: '2026-10-02T16:00:00Z',
    excerpt: 'Aucun conseiller ni automate ne demande de mot de passe ou code confidentiel par SMS ou email.',
  },
  {
    id: 'kb-45',
    title: 'Programme Avantages Fidélité & Rétention',
    category: 'Commercial',
    chunks: 9,
    updatedAt: '2026-07-10T11:20:00Z',
    excerpt: 'Les clients de plus de 3 ans d’ancienneté bénéficient d’une remise de 15% pendant 12 mois ou d’un pack data offert.',
  },
]

const SAMPLE_MESSAGES = {
  calme: 'Bonjour, pourriez-vous m’expliquer les options de mon forfait ?',
  impatient: 'Ça fait 3 jours que j’attends mon remboursement, c’est pour quand ?',
  nerveux: 'J’ai reçu un SMS bizarre au sujet de mon compte, est-ce grave ?',
  mecontent: 'Je voudrais comprendre pourquoi ma facture est plus élevée ce mois-ci ?',
  fidele: 'Je suis client depuis 10 ans, avez-vous une offre de fidélité ?',
  confus: 'Je ne comprends pas la différence entre mes deux lignes sur la facture.',
  exigeant: 'Donnez-moi le détail exact de chaque frais prélevé ce trimestre.',
  heureux: 'Bonjour ! Je suis très satisfait de vos services et j’aimerais découvrir vos nouvelles offres.',
}

// Conversation follow-up messages per profile for multi-turn mode
const CONVERSATION_FOLLOWUPS = {
  calme: [
    'D\'accord, merci pour cette explication. Et concernant les options supplémentaires ?',
    'Je vois. Pourriez-vous me confirmer que tout est bien en ordre maintenant ?',
    'Parfait. Une dernière question : comment je peux suivre mon dossier ?',
    'Merci beaucoup pour votre aide, c\'était très clair.',
  ],
  impatient: [
    'Oui mais concrètement, ça va prendre combien de temps encore ?!',
    'Vous m\'aviez dit pareil la dernière fois et rien n\'a changé…',
    'Je veux parler à un responsable si ce n\'est pas réglé immédiatement.',
    'Bon… j\'espère que cette fois c\'est la bonne. Je note votre nom.',
  ],
  nerveux: [
    'Vous êtes sûr que mon compte est bien sécurisé ? J\'ai vraiment peur…',
    'Et si quelqu\'un a déjà accédé à mes données, comment je le sais ?',
    'D\'accord… mais est-ce que je dois changer tous mes mots de passe quand même ?',
    'Merci, ça me rassure un peu. Je vais rester vigilant.',
  ],
  mecontent: [
    'C\'est pas suffisant comme explication ! Je veux un geste commercial.',
    'Vous vous rendez compte que c\'est la troisième fois que j\'appelle ?!',
    'Je vais laisser un avis négatif si rien n\'est fait aujourd\'hui.',
    'Bon, je vais accepter cette proposition mais c\'est la dernière fois.',
  ],
  fidele: [
    'Justement, après 10 ans de fidélité, j\'attendais un geste de votre part.',
    'Est-ce qu\'il y a un programme VIP ou des avantages exclusifs ?',
    'D\'accord, ça me semble intéressant. Comment on procède ?',
    'Merci, c\'est agréable de se sentir valorisé comme client.',
  ],
  confus: [
    'Attendez, je ne comprends toujours pas bien la différence entre les deux…',
    'Donc si je résume… c\'est bien ça que vous me dites ?',
    'Ah d\'accord ! C\'est plus clair maintenant. Et pour le reste ?',
    'OK je pense que j\'ai compris. Merci d\'avoir pris le temps.',
  ],
  exigeant: [
    'Je veux le détail ligne par ligne, pas un résumé approximatif.',
    'Et la référence légale qui justifie ce prélèvement, c\'est quoi exactement ?',
    'Envoyez-moi tout ça par écrit avec les numéros de dossier précis.',
    'Bien, c\'est plus professionnel comme réponse. Je vérifie et je reviens.',
  ],
  heureux: [
    'Super, merci beaucoup pour cette explication claire et rapide !',
    'C\'est parfait, votre conseiller m\'a déjà fait une super impression.',
    'Avez-vous d\'autres options avantageuses ou offres de fidélité à me conseiller ?',
    'Un grand merci pour votre accompagnement chaleureux et très professionnel !',
  ],
}

const ADVISOR_FOLLOWUPS = [
  'Bien sûr, je comprends votre préoccupation. Permettez-moi de vérifier les détails pour vous apporter une réponse précise.',
  'Je vous confirme que votre dossier est en cours de traitement. Voici les prochaines étapes que nous allons suivre ensemble.',
  'Absolument, je vais m\'assurer que tout soit bien résolu de votre côté. N\'hésitez pas si vous avez d\'autres questions.',
  'Je vous remercie pour votre patience. Votre demande a bien été prise en compte et le nécessaire est fait.',
  'Rassurez-vous, nous prenons votre situation très au sérieux. Je vais personnellement suivre ce dossier.',
]

// Relances du client selon ce que le conseiller vient de dire (même profil sur tous les tours)
const REACTIONS = {
  offre: {
    calme: 'Merci pour cette proposition. Pouvez-vous me préciser les conditions exactes et la date d\'application ?',
    impatient: 'Un geste, d\'accord, mais quand est-ce que ça s\'applique concrètement ?! Je ne veux plus relancer.',
    nerveux: 'D\'accord… mais êtes-vous sûr qu\'il n\'y aura pas de frais cachés derrière cette proposition ?',
    mecontent: 'C\'est tout ce que vous proposez ? Après ce que j\'ai subi, ce geste est insuffisant !',
    fidele: 'Merci, mais après toutes ces années, y a-t-il un avantage fidélité en plus de ce geste ?',
    confus: 'Je ne suis pas sûr de comprendre cette proposition. Qu\'est-ce que ça change sur ma facture ?',
    exigeant: 'Je veux cette proposition par écrit, avec le montant exact et la référence de la procédure.',
    heureux: 'C\'est très généreux, merci ! Y a-t-il d\'autres avantages dont je pourrais profiter ?',
  },
  attente: {
    calme: 'Très bien. Combien de temps faut-il compter avant d\'avoir une confirmation ?',
    impatient: 'Vous « vérifiez » depuis tout à l\'heure… Donnez-moi une échéance précise, maintenant !',
    nerveux: 'Et pendant ce temps-là, il n\'y a aucun risque pour mon compte, n\'est-ce pas ?',
    mecontent: 'On me répète toujours « c\'est en cours » ! Je veux un engagement ferme aujourd\'hui.',
    fidele: 'Je comprends, mais pour un client de longue date, pouvez-vous accélérer le traitement ?',
    confus: 'Je ne vois pas bien les étapes… Que va-t-il se passer exactement ensuite ?',
    exigeant: 'Quel est le délai contractuel exact, et qui est responsable de mon dossier ?',
    heureux: 'Pas de souci, merci pour votre réactivité ! Comment serai-je informé de la suite ?',
  },
  securite: {
    calme: 'Merci pour ces précisions. Dois-je faire quelque chose de mon côté par précaution ?',
    impatient: 'Bon, et concrètement je fais quoi tout de suite pour que ça s\'arrête ?!',
    nerveux: 'Vous êtes sûr qu\'il n\'y a pas eu d\'accès à mon compte ? Je suis vraiment inquiet…',
    mecontent: 'Comment un tel SMS a-t-il pu m\'arriver ? C\'est un manque de sécurité de votre part !',
    fidele: 'Après tant d\'années chez vous, je compte sur votre vigilance. Que faites-vous pour me protéger ?',
    confus: 'Je ne comprends pas bien ce qu\'est le phishing. Comment reconnaître un faux message ?',
    exigeant: 'Quelles mesures techniques précises avez-vous prises ? Je veux un compte rendu détaillé.',
    heureux: 'Merci pour votre vigilance, c\'est rassurant ! Y a-t-il des bonnes pratiques à connaître ?',
  },
}

function detectReaction(answer = '') {
  const a = answer.toLowerCase()
  if (/phishing|sécuris|bloqu|sms/.test(a)) return 'securite'
  if (/geste|€|avoir|remise|offre|avantage|forfait/.test(a)) return 'offre'
  if (/vérifi|en cours|délai|crédit|patience|traitement|prochaines/.test(a)) return 'attente'
  return null
}

// Question suivante du client : dépend de la dernière réponse du conseiller.
// Le dernier tour est un message de clôture.
function nextClientQuestion({ profile, turn, count, history }) {
  const generic = CONVERSATION_FOLLOWUPS[profile] || CONVERSATION_FOLLOWUPS.calme
  if (turn >= count) return generic[generic.length - 1]
  const asked = history.map((h) => h.clientMessage)
  const reaction = detectReaction(history[history.length - 1]?.advisorAnswer)
  const reactive = reaction && (REACTIONS[reaction][profile] || REACTIONS[reaction].calme)
  if (reactive && !asked.includes(reactive)) return reactive
  const fallback = generic.slice(0, -1).find((m) => !asked.includes(m))
  return fallback || generic[Math.min(turn - 2, generic.length - 2)]
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const rnd = (a, b) => Math.round(a + Math.random() * (b - a))

let history = [
  { id: 's-1', title: 'Facture plus élevée ce mois-ci', profile: 'mecontent', score: 85, createdAt: new Date().toISOString() },
  { id: 's-2', title: 'Remboursement en attente', profile: 'impatient', score: 72, createdAt: new Date().toISOString() },
  { id: 's-3', title: 'SMS suspect sur mon compte', profile: 'nerveux', score: 91, createdAt: new Date(Date.now() - 864e5).toISOString() },
  { id: 's-4', title: 'Offre de fidélité', profile: 'fidele', score: 88, createdAt: new Date(Date.now() - 864e5).toISOString() },
  { id: 's-5', title: 'Deux lignes sur la facture', profile: 'confus', score: 64, createdAt: new Date(Date.now() - 4 * 864e5).toISOString() },
]

// Full results keyed by id for getSimulation
const simulationStore = {}

export const mock = {
  async getProfiles() { await wait(120); return PROFILES },
  async getKbDocuments() { await wait(120); return KB_DOCUMENTS },
  async getConversations() { await wait(120); return [...history] },

  async getSimulation(id) {
    await wait(120)
    if (simulationStore[id]) return simulationStore[id]
    const conv = history.find((h) => h.id === id)
    if (!conv) throw new Error('Simulation introuvable')
    const criteria = { pertinence: 82, exactitude: 79, groundedness: 85, empathie: 74, clarte: 88, conformite: 91 }
    return {
      id: conv.id, createdAt: conv.createdAt,
      request: { profile: conv.profile, message: conv.title, intent: 'reclamation', entities: {} },
      response: {
        answer: "Je comprends votre situation. Voici les éléments disponibles pour vous aider au mieux.",
        intent: 'reclamation', sources: [], latencyMs: 1200,
      },
      evaluation: {
        globalScore: conv.score,
        criteria,
        strengths: ['Réponse claire'],
        improvements: ['Proposer une action concrète'],
        recommendations: ['Suivi par e-mail'],
      },
      decision: { problems: [], actions: [] },
    }
  },

  async getKpi() {
    await wait(150)
    return {
      qualiteReponses: 82.4,
      tauxResolution: 76.1,
      tempsTraitementSec: 4.2,
      tauxEscalade: 8.5,
      satisfactionClient: 4.1,
      performanceParProfil: PROFILES.map((p) => ({ profile: p.id, score: rnd(60, 95), count: rnd(12, 80) })),
    }
  },

  // 1. Client Simulator Agent (unitaire)
  // history = échanges précédents [{ clientMessage, advisorAnswer }] : si fourni, génère la question suivante du même client
  async runClientSimulator({ profile = 'mecontent', topic = 'facturation', customPrompt = '', urgency = 'moyenne', isConversation = false, messageCount = 3, history = [] }) {
    await wait(700)
    if (history.length > 0) {
      const turn = history.length + 1
      const message = nextClientQuestion({ profile, turn, count: Math.max(messageCount, turn), history })
      return {
        agent: 'Client Simulator Agent',
        profile,
        profileLabel: PROFILES.find((p) => p.id === profile)?.label || profile,
        topic,
        urgency,
        turn,
        message,
        generatedAt: new Date().toISOString(),
      }
    }
    const baseTopic = TOPICS.find((t) => t.id === topic)
    let generatedMessage = customPrompt.trim() || baseTopic?.defaultMsg || SAMPLE_MESSAGES[profile] || 'Bonjour, j’ai une question sur mon compte.'
    
    // Add persona flavor if custom wasn't provided
    if (!customPrompt.trim()) {
      if (profile === 'impatient') generatedMessage = 'URGENT : ' + generatedMessage + ' Ça fait trop longtemps que ça dure !'
      if (profile === 'nerveux') generatedMessage = 'Bonjour, je suis très inquiet... ' + generatedMessage + ' Est-ce que mes données sont protégées ?'
      if (profile === 'mecontent') generatedMessage = 'Je suis extrêmement mécontent ! ' + generatedMessage + ' C’est inacceptable.'
      if (profile === 'exigeant') generatedMessage = 'Veuillez me transmettre immédiatement le détail complet et chiffré : ' + generatedMessage
      if (profile === 'heureux') generatedMessage = 'Bonjour avec le grand sourire ! ' + generatedMessage + ' Je tenais à vous remercier chaleureusement.'
    }

    const intentMap = {
      facturation: 'reclamation_facture',
      remboursement: 'suivi_remboursement',
      securite: 'alerte_securite_phishing',
      fidelite: 'demande_geste_commercial',
      technique: 'incident_technique',
      resiliation: 'demande_resiliation',
    }

    const entitiesMap = {
      facturation: { objet: 'facture', periode: 'mois en cours', anomalie: 'surcoût' },
      remboursement: { statut: 'en_attente', delai_declare: '3 jours', montant_estime: '45€' },
      securite: { canal: 'SMS', menace_suspectee: 'phishing', compte_cible: 'principal' },
      fidelite: { anciennete: '10 ans', offre_cible: 'remise_annuelle' },
      technique: { equipement: 'box/mobile', impact: 'coupure', gravite: 'elevee' },
      resiliation: { motif: 'tarifaire', sans_frais: 'vrai' },
    }

    const count = Math.max(1, Math.min(5, messageCount))
    const followups = CONVERSATION_FOLLOWUPS[profile] || CONVERSATION_FOLLOWUPS.calme
    const conversationMessages = [generatedMessage, ...followups.slice(0, count - 1)]

    return {
      agent: 'Client Simulator Agent',
      profile,
      profileLabel: PROFILES.find((p) => p.id === profile)?.label || profile,
      topic,
      urgency,
      message: generatedMessage,
      isConversation,
      messageCount: count,
      conversationMessages: isConversation ? conversationMessages : [generatedMessage],
      intent: intentMap[topic] || 'demande_generale',
      entities: entitiesMap[topic] || { objet: 'compte' },
      sentiment: profile === 'mecontent' ? 'negatif_fort' : profile === 'heureux' ? 'tres_positif' : profile === 'nerveux' ? 'anxieux' : profile === 'impatient' ? 'agace' : 'neutre',
      tone: profile === 'heureux' ? 'chaleureux et enthousiaste' : profile === 'calme' ? 'posé et structuré' : profile === 'exigeant' ? 'rigoureux et autoritaire' : 'expressif',
      generatedAt: new Date().toISOString(),
    }
  },

  // 2. Customer Advisor Agent (unitaire RAG & conversation multi-tours)
  // turnOffset = rang (0 = 1er tour) du premier message transmis, pour répondre un tour à la fois
  async runCustomerAdvisor({ profile = 'mecontent', message, topic = 'facturation', rag = true, conversationMessages, isConversation = false, messageCount = 1, turnOffset = 0 }) {
    await wait(800)
    const msgs = (conversationMessages && conversationMessages.length > 0)
      ? conversationMessages
      : (message ? [message] : [SAMPLE_MESSAGES[profile] || 'Bonjour, j’ai une demande concernant mes services.'])

    const isMultiTurn = isConversation || msgs.length > 1
    const count = Math.min(5, Math.max(1, isMultiTurn ? (msgs.length || messageCount) : 1))
    const actualMsgs = msgs.slice(0, count)

    // Pick KB sources matching topic
    let sources = []
    const firstMsg = actualMsgs[0] || ''
    if (rag) {
      if (topic === 'facturation' || firstMsg.toLowerCase().includes('facture')) {
        sources = [
          { id: 'kb-12', title: 'Grille tarifaire et dépassements 2026', score: 0.94, snippet: 'Dépassement data facturé 0,05€/Mo. Alerte SMS dès 80%.' },
          { id: 'kb-07', title: 'Procédure contestation et remise', score: 0.88, snippet: 'Possibilité d’un avoir commercial de 30€ max sur 1er dépassement.' },
        ]
      } else if (topic === 'remboursement' || firstMsg.toLowerCase().includes('remboursement')) {
        sources = [
          { id: 'kb-21', title: 'Délais de traitement des remboursements', score: 0.96, snippet: 'Validation 48h ouvrées, crédit sous 3 à 5 jours bancaires.' },
        ]
      } else if (topic === 'securite' || firstMsg.toLowerCase().includes('sms') || firstMsg.toLowerCase().includes('phishing')) {
        sources = [
          { id: 'kb-34', title: 'Guide d’authentification et sécurité', score: 0.97, snippet: 'Aucune demande d’identifiant ou mot de passe par SMS.' },
        ]
      } else {
        sources = [
          { id: 'kb-45', title: 'Programme Avantages Fidélité', score: 0.89, snippet: 'Remise 15% ou pack data pour les abonnés de plus de 3 ans.' },
        ]
      }
    }

    const getFirstAnswer = (msg) => {
      if (profile === 'heureux') {
        return `Bonjour et merci infiniment pour vos encouragements ! Nous sommes ravis de votre satisfaction. Concernant votre demande (${topic}), je vous confirme que nos nouvelles offres et avantages fidélité sont d'ores et déjà disponibles sur votre compte.`
      }
      if (msg.toLowerCase().includes('facture')) {
        return rag
          ? `Bonjour, je comprends tout à fait votre étonnement face à cette facture. D’après nos relevés, le surcoût provient d'un dépassement de 3,2 Go d'internet mobile hors forfait ainsi que de l'entrée en vigueur de la nouvelle grille tarifaire 2026 (référencée dans notre base kb-12). Conformément à notre politique de satisfaction (kb-07), je peux dès aujourd'hui vous accorder un geste commercial de 15 € et basculer votre offre sur le forfait supérieur sans frais.`
          : `Bonjour, je vois que votre facture comporte un montant supérieur à la normale. Il s'agit probablement d'une consommation hors forfait. Merci de vérifier vos détails de consommation dans votre espace client.`
      } else if (msg.toLowerCase().includes('remboursement')) {
        return rag
          ? `Bonjour, je comprends votre attente. Votre dossier de remboursement a bien été validé le 12 courant par notre service comptabilité. Conformément aux délais bancaires usuels de 3 à 5 jours ouvrés (kb-21), les fonds seront crédités sur votre compte d'ici demain au plus tard.`
          : `Bonjour, les remboursements prennent en général quelques jours. Votre demande est en cours de traitement.`
      } else if (msg.toLowerCase().includes('sms') || msg.toLowerCase().includes('suspect')) {
        return rag
          ? `Bonjour, rassurez-vous : nous n'avons procédé à aucun débit anormal. Il s'agit d'une tentative de phishing par faux SMS qui ne provient pas de nos services (procédure kb-34). Ne cliquez sur aucun lien. Votre compte est sécurisé et nous venons de bloquer le numéro émetteur sur nos passerelles.`
          : `Bonjour, faites attention, nous ne demandons jamais vos codes secrets. Supprimez ce SMS.`
      } else {
        return `Bonjour, je vous remercie pour votre message. J'ai bien analysé votre demande et je reste à votre entière disposition pour vous guider et vous apporter la solution la plus adaptée.`
      }
    }

    const conversationExchanges = actualMsgs.map((clientMsg, i) => {
      const idx = i + turnOffset
      let advisorAnswer = ''
      if (idx === 0) {
        advisorAnswer = getFirstAnswer(clientMsg)
      } else if (idx === 1) {
        advisorAnswer = profile === 'mecontent'
          ? `Je comprends parfaitement votre agacement face à cette situation. J'ai immédiatement appliqué la déduction de 15 € sur votre relevé et je consigne votre réclamation en priorité dans votre dossier.`
          : profile === 'heureux'
          ? `C'est un réel plaisir de vous accompagner ! Sachez que nos conseillers s'efforcent toujours d'offrir une expérience de premier ordre. Voici les détails additionnels que vous souhaitiez.`
          : ADVISOR_FOLLOWUPS[0]
      } else if (idx === 2) {
        advisorAnswer = profile === 'mecontent'
          ? `Rassurez-vous, votre geste commercial est définitivement validé et le remboursement est enclenché sous 48h. Un récapitulatif complet vient de vous être adressé par email.`
          : profile === 'heureux'
          ? `Merci encore pour votre enthousiasme et votre fidélité ! Tout est parfaitement en ordre sur votre profil client.`
          : ADVISOR_FOLLOWUPS[1]
      } else {
        advisorAnswer = ADVISOR_FOLLOWUPS[Math.min(idx, ADVISOR_FOLLOWUPS.length - 1)]
      }

      return {
        turn: idx + 1,
        clientMessage: clientMsg,
        advisorAnswer,
        sources: (idx === 0 && rag) ? sources : [],
        latencyMs: rnd(650, 1300),
      }
    })

    const totalLatency = conversationExchanges.reduce((acc, curr) => acc + curr.latencyMs, 0)
    const lastAnswer = conversationExchanges[conversationExchanges.length - 1].advisorAnswer

    return {
      agent: 'Agent Conseiller Client',
      answer: lastAnswer,
      conversationExchanges,
      isConversation: isMultiTurn,
      messageCount: actualMsgs.length,
      intent: topic || 'assistance_client',
      ragActive: rag,
      sources,
      latencyMs: totalLatency,
      model: 'Conseiller Virtuel Relation Client',
      confidence: rnd(88, 99) / 100,
      generatedAt: new Date().toISOString(),
    }
  },

  // 3b. Analyste Qualité : routes annexes (mode démo, aucune inférence réelle)
  async getQualityHealth() { await wait(100); return { service: 'quality-analyst', status: 'mock', llmConfigured: false, lora: { enabled: false } } },
  async getLoraExperiment() { await wait(100); return { status: 'mock' } },
  async runLoraCheck() { await wait(300); return { status: 'disabled', label: null, message: 'Mode démo : LoRA non exécuté.' } },
  async runSecondJudge() { await wait(300); return { status: 'disabled', message: 'Mode démo : second juge non exécuté.' } },

  // 3. Quality Analyst Agent (unitaire)
  async runQualityAnalyst({ request, response }) {
    await wait(800)
    const reqText = request?.message || ''
    const resText = response?.answer || ''
    const hasSources = (response?.sources || []).length > 0
    const profile = request?.profile || 'mecontent'

    const pertinence = rnd(78, 96)
    const exactitude = hasSources ? rnd(84, 98) : rnd(65, 82)
    const groundedness = hasSources ? rnd(82, 97) : rnd(50, 70)
    const empathie = profile === 'mecontent' || profile === 'nerveux' ? rnd(70, 92) : rnd(80, 95)
    const clarte = rnd(80, 98)
    const conformite = rnd(85, 99)

    const criteria = { pertinence, exactitude, groundedness, empathie, clarte, conformite }
    const globalScore = Math.round(Object.values(criteria).reduce((a, b) => a + b, 0) / 6)

    const strengths = [
      'Explication factuelle et structurée',
      ...(hasSources ? ['Citation précise des fiches documentaires'] : ['Ton courtois']),
      ...(clarte > 85 ? ['Formulation accessible et sans jargon'] : []),
    ]

    const improvements = [
      ...(empathie < 78 ? ['Renforcer l’empathie dès la phrase d’introduction'] : []),
      ...(!hasSources ? ['Consulter la base documentaire pour étayer la réponse par les procédures officielles'] : []),
      ...(globalScore < 80 ? ['Formuler une proposition d’action concrète avec délai précis'] : ['Préciser la voie de recours disponible']),
    ]

    const recommendations = [
      'Envoyer un récapitulatif par e-mail ou SMS',
      'Consigner la contestation dans le CRM client',
      'Proposer un rappel planifié si question résiduelle',
    ]

    return {
      agent: 'Quality Analyst Agent',
      globalScore,
      criteria,
      strengths,
      improvements,
      recommendations,
      complianceCheck: conformite >= 80 ? 'CONFORME' : 'ATTENTION_CONFORMITE',
      evaluatedAt: new Date().toISOString(),
    }
  },

  // 4. Workforce Manager Agent (unitaire)
  async runWorkforceManager({ evaluation, request, kpi }) {
    await wait(750)
    const score = evaluation?.globalScore ?? 80
    const empathyScore = evaluation?.criteria?.empathie ?? 75
    const groundednessScore = evaluation?.criteria?.groundedness ?? 80
    const profile = request?.profile || 'mecontent'

    const problems = []
    const actions = []

    if (score < 75) {
      problems.push(`Score global insuffisant (${score}/100) en dessous du seuil cible (75)`)
      actions.push({
        type: 'escalade_humain',
        description: 'Transférer le dossier vers un conseiller senior niveau 2 pour prise en charge personnalisée.',
        priority: 'haute',
        responsible: 'Superviseur Équipe N2',
      })
    }

    if (empathyScore < 75) {
      problems.push(`Déficit d'empathie détecté (${empathyScore}/100) face à un profil ${profile}`)
      actions.push({
        type: 'ajuster_reponse',
        description: `Ajuster les consignes de tonalité (prompt système) pour le persona ${profile}.`,
        priority: 'moyenne',
        responsible: 'Lead Prompt Engineer',
      })
    }

    if (groundednessScore < 75) {
      problems.push(`Ancrage documentaire insuffisant (${groundednessScore}/100)`)
      actions.push({
        type: 'signaler_kb',
        description: 'Compléter et mettre à jour la fiche documentaire correspondante dans la base de connaissances interne.',
        priority: 'moyenne',
        responsible: 'Responsable Base Documentaire',
      })
    }

    // Default proactive continuous improvement actions
    actions.push({
      type: 'formation',
      description: 'Programmer un module de micro-learning de 15 min sur la désescalade émotionnelle.',
      priority: 'basse',
      responsible: 'RH & Formation',
    })

    return {
      agent: 'Workforce Manager Agent',
      auditScore: score,
      status: score >= 75 ? 'OPTIMAL' : 'INTERVENTION_REQUISE',
      problems,
      actions,
      workforceSummary: {
        staffingImpact: score < 75 ? '+1 escalade vers N2' : 'Traitement 100% autonome',
        trainingModuleSuggested: empathyScore < 75 ? 'Module Empathie & Posture relationnelle' : 'Veille réglementaire continue',
        kbUpdateRequired: groundednessScore < 75,
      },
      decidedAt: new Date().toISOString(),
    }
  },

  // Simulation complète chaînée (conserve l'historique global)
  async runSimulation({ profile = 'mecontent', message, topic = 'facturation', rag = true }) {
    await wait(1200)
    const msg = message || SAMPLE_MESSAGES[profile]
    const criteria = {
      pertinence: rnd(75, 98), exactitude: rnd(70, 95), groundedness: rnd(65, 95),
      empathie: rnd(55, 95), clarte: rnd(70, 98), conformite: rnd(80, 100),
    }
    const globalScore = Math.round(Object.values(criteria).reduce((a, b) => a + b, 0) / 6)
    const result = {
      id: 's-' + Date.now(),
      createdAt: new Date().toISOString(),
      request: { profile, message: msg, intent: 'reclamation_facture', entities: { periode: 'ce mois-ci', objet: 'facture' } },
      response: {
        answer:
          'Je comprends votre inquiétude. Votre facture est plus élevée en raison d’une augmentation de votre consommation de données (+3,2 Go hors forfait) et de l’application de la nouvelle grille tarifaire depuis le 1er du mois. Je peux vous proposer une option data adaptée pour éviter ce dépassement.',
        intent: 'reclamation_facture',
        sources: [
          { id: 'kb-12', title: 'Grille tarifaire 2026', score: 0.91 },
          { id: 'kb-07', title: 'Procédure hors forfait', score: 0.84 },
        ],
        latencyMs: rnd(900, 2400),
      },
      evaluation: {
        globalScore,
        criteria,
        strengths: ['Réponse claire et structurée', 'Sources pertinentes citées'],
        improvements: criteria.empathie < 75 ? ['Renforcer l’empathie en ouverture'] : ['Proposer une action concrète plus tôt'],
        recommendations: ['Ajouter le montant exact du dépassement', 'Proposer un suivi par e-mail'],
      },
      decision: {
        problems: globalScore < 75 ? ['Score qualité sous le seuil (75)'] : [],
        actions: [
          { type: 'ajuster_reponse', description: 'Ajuster le ton pour le profil ' + (PROFILES.find((p) => p.id === profile)?.label || profile).toLowerCase(), priority: 'moyenne' },
          { type: 'signaler_kb', description: 'Compléter la fiche « hors forfait »', priority: 'basse' },
          ...(globalScore < 75 ? [{ type: 'escalade_humain', description: 'Escalader vers un conseiller humain', priority: 'haute' }] : []),
        ],
      },
    }
    history = [{ id: result.id, title: msg.slice(0, 40), profile, score: globalScore, createdAt: result.createdAt }, ...history]
    simulationStore[result.id] = result
    return result
  },

  // Conversation multi-tour : boucle agent simulateur (question) → agent conseiller (réponse), `count` fois, même profil
  async runConversationSimulation({ profile = 'mecontent', message, topic = 'facturation', rag = true, messageCount = 3 }) {
    const count = Math.max(1, Math.min(5, messageCount))
    const turns = []

    for (let i = 0; i < count; i++) {
      const sim = await mock.runClientSimulator({
        profile, topic, messageCount: count,
        customPrompt: i === 0 ? message || SAMPLE_MESSAGES[profile] : '',
        history: turns,
      })
      const adv = await mock.runCustomerAdvisor({
        profile, topic, rag,
        conversationMessages: [sim.message],
        isConversation: true,
        turnOffset: i,
      })
      turns.push({ clientMessage: sim.message, advisorAnswer: adv.answer })
    }

    return mock.saveConversation({ profile, topic, rag, turns })
  },

  // Enregistre une conversation terminée (tours [{ clientMessage, advisorAnswer }]) : évaluation, décision et historique.
  // Appelé aussi depuis le parcours Simulateur ↔ Conseiller ; un `id` déjà connu remplace l'entrée existante.
  async saveConversation({ id = 'conv-' + Date.now(), profile = 'mecontent', topic = 'facturation', rag = true, turns }) {
    await wait(150)
    const count = turns.length
    const msg = turns[0].clientMessage
    const exchanges = turns.map((t, i) => {
      const criteria = {
        pertinence: rnd(75, 98), exactitude: rnd(70, 95), groundedness: rnd(65, 95),
        empathie: rnd(55, 95), clarte: rnd(70, 98), conformite: rnd(80, 100),
      }
      return {
        turn: i + 1,
        client: {
          message: t.clientMessage,
          profile,
          profileLabel: PROFILES.find((p) => p.id === profile)?.label || profile,
          sentiment: i === 0 ? (profile === 'mecontent' ? 'negatif_fort' : profile === 'heureux' ? 'tres_positif' : 'neutre') : (i >= count - 1 ? (profile === 'heureux' ? 'enchante' : 'apaisé') : 'neutre'),
        },
        advisor: {
          answer: t.advisorAnswer,
          sources: rag && i === 0 ? [
            { id: 'kb-12', title: 'Grille tarifaire 2026', score: 0.91 },
            { id: 'kb-07', title: 'Procédure hors forfait', score: 0.84 },
          ] : [],
          latencyMs: rnd(650, 1800),
        },
        evaluation: {
          globalScore: Math.round(Object.values(criteria).reduce((a, b) => a + b, 0) / 6),
          criteria,
        },
      }
    })

    // Overall evaluation = average of all exchanges
    const avgScore = Math.round(exchanges.reduce((s, e) => s + e.evaluation.globalScore, 0) / count)
    const avg = (k) => Math.round(exchanges.reduce((s, e) => s + e.evaluation.criteria[k], 0) / count)

    const result = {
      id,
      createdAt: new Date().toISOString(),
      isConversation: true,
      messageCount: count,
      request: { profile, message: msg, intent: 'reclamation_facture', entities: { periode: 'ce mois-ci', objet: 'facture' } },
      exchanges,
      response: {
        answer: exchanges[count - 1].advisor.answer,
        intent: 'reclamation_facture',
        sources: exchanges[0].advisor.sources,
        latencyMs: exchanges.reduce((s, e) => s + e.advisor.latencyMs, 0),
      },
      evaluation: {
        globalScore: avgScore,
        criteria: {
          pertinence: avg('pertinence'), exactitude: avg('exactitude'), groundedness: avg('groundedness'),
          empathie: avg('empathie'), clarte: avg('clarte'), conformite: avg('conformite'),
        },
        strengths: ['Conversation multi-tour cohérente', 'Adaptation au profil client'],
        improvements: avgScore < 80 ? ['Améliorer la constance qualitative sur les échanges successifs'] : ['Proposer un récapitulatif en fin de conversation'],
        recommendations: ['Envoyer un récapitulatif par e-mail', 'Consigner l\'échange complet dans le CRM'],
      },
      decision: {
        problems: avgScore < 75 ? ['Score moyen de conversation sous le seuil (75)'] : [],
        actions: [
          { type: 'ajuster_reponse', description: 'Ajuster le ton pour le profil ' + (PROFILES.find((p) => p.id === profile)?.label || profile).toLowerCase(), priority: 'moyenne' },
          ...(avgScore < 75 ? [{ type: 'escalade_humain', description: 'Escalader vers un conseiller humain', priority: 'haute' }] : []),
        ],
      },
    }

    const entry = { id, title: '💬 ' + msg.slice(0, 35) + ` (${count} msg)`, profile, score: avgScore, createdAt: result.createdAt }
    history = [entry, ...history.filter((h) => h.id !== id)]
    simulationStore[id] = result
    return result
  },
}
