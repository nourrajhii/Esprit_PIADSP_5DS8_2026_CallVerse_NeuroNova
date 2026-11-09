"""Schémas Pydantic de l'API (requêtes et réponses)."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

ProfileType = Literal["calme", "impatient", "nerveux", "mecontent", "fidele", "confus", "exigeant", "heureux"]
UrgencyType = Literal["basse", "moyenne", "haute"]

class HistoryTurn(BaseModel):
    role: Literal["client", "advisor"]
    content: str


class AdvisorRequest(BaseModel):
    profile: ProfileType = "calme"
    message: str = Field(min_length=1)
    topic: Optional[str] = None
    rag: bool = True
    history: list[HistoryTurn] = []
    # champs envoyés par le front (Conseiller Client)
    isConversation: bool = False
    conversationMessages: Optional[list[str]] = None  # session saisie à la main : plusieurs messages d'un coup
    conversationId: Optional[str] = None              # conversation menée page par page (id reçu du Client Simulator)
    turnOffset: int = 0                               # rang du message dans la conversation (0 = 1er)


class Source(BaseModel):
    id: str
    title: str
    score: float
    module: Optional[str] = None
    snippet: Optional[str] = None
    illustrative: bool = False
    expired: bool = False


class Product(BaseModel):
    name: str
    brand: str
    price: str
    inStock: bool
    url: str
    description: str = ""
    fullDescription: str = ""
    score: float = 0


class ProductContext(BaseModel):
    scenario: Literal["in_stock", "only_out_of_stock", "no_match"]
    budgetMax: Optional[float] = None
    inStock: list[Product] = []
    outOfStock: list[Product] = []


class ToolStep(BaseModel):
    step: int
    tool: str
    args: dict = {}
    observation: str = ""
    modules: list[str] = []
    source: Literal["agent", "thematique"] = "agent"
    ms: int = 0


class AdvisorResponse(BaseModel):
    answer: str
    intent: str
    sources: list[Source] = []
    latencyMs: int
    model: Optional[str] = None
    mode: Optional[str] = None
    urgent: bool = False
    modules: list[str] = []
    specialists: list[str] = []
    products: Optional[ProductContext] = None
    steps: list[ToolStep] = []
    # champs lus par le front (page Conseiller Client)
    agent: str = "Agent Conseiller Client"
    ragActive: bool = True
    confidence: Optional[float] = None  # meilleur score de similarité des sources (absent si aucune source)
    generatedAt: Optional[str] = None
    isConversation: bool = False
    messageCount: int = 1
    conversationExchanges: list[dict] = []


class ConversationRequest(BaseModel):
    profile: ProfileType = "calme"
    topic: Optional[str] = None
    rag: bool = True
    messages: list[str] = Field(min_length=1, max_length=5)


class ConversationTurn(BaseModel):
    turn: int
    clientMessage: str
    advisor: AdvisorResponse


class ConversationResponse(BaseModel):
    turns: list[ConversationTurn]
    latencyMs: int


class KbDocument(BaseModel):
    id: str
    title: str
    category: str
    excerpt: str
    chunks: int = 1


# --- Client Simulator -------------------------------------------------------
class ClientSimRequest(BaseModel):
    profile: ProfileType = "mecontent"
    topic: Optional[str] = None
    urgency: UrgencyType = "moyenne"
    customPrompt: Optional[str] = None
    isConversation: bool = False
    messageCount: int = Field(default=1, ge=1, le=5)
    # suite d'une conversation : id reçu avec le 1er message + réponse du conseiller
    conversationId: Optional[str] = None
    advisorMessage: Optional[str] = None
    history: list = []  # envoyé par le front, ignoré : l'historique est gardé côté serveur (SESSIONS)


class SaveConversationTurn(BaseModel):
    clientMessage: str
    advisorAnswer: str


class SaveConversationRequest(BaseModel):
    id: str                                  # id choisi par le front (repli si la conversation serveur est inconnue)
    conversationId: Optional[str] = None     # id de la conversation côté serveur (reçu du Client Simulator)
    profile: ProfileType = "mecontent"
    topic: Optional[str] = None
    rag: bool = True
    turns: list[SaveConversationTurn] = Field(min_length=1, max_length=5)


class SimulationRequest(BaseModel):
    profile: ProfileType = "mecontent"
    topic: Optional[str] = None
    urgency: UrgencyType = "moyenne"
    rag: bool = True
    conversationMode: bool = False      # False = 1 seul échange, quel que soit messageCount
    messageCount: int = Field(default=3, ge=1, le=5)
    message: Optional[str] = None       # message saisi dans le Composer du front
    firstMessage: Optional[str] = None  # idem (nom historique) ; vide = généré par le Client Simulator
    customPrompt: Optional[str] = None
