#!/usr/bin/env python3
"""
PIADSP - Agent MODULAR RAG E-commerce + Parapharmacie (MaPara Tunisie) avec Gemini / Groq.

Mode AGENTIC (par défaut) : le LLM appelle lui-même les outils de recherche (boucle raisonnement -> outil -> observation).
Index vectoriels : ChromaDB (base vectorielle persistante dans .cache/chroma, similarité cosinus).
Version "simple" (sans fine-tuning) avec CHAÎNE DE SECOURS entre modèles : quand le quota journalier d'un
modèle est épuisé (429 / PerDay / TPD), l'agent bascule automatiquement sur le suivant (LLM_CHAIN dans .env).

Architecture modulaire : un routeur LLM choisit un ou plusieurs modules, chaque module a son propre
index vectoriel et sa propre logique de récupération, puis un générateur unique compose la réponse.

  Modules "cœur" :
    - product  : CONSEIL PRODUIT (catalogue en stock + rupture, priorité au stock, budget respecté)
    - symptom  : SYMPTÔMES -> spécialités médicales (diseases.csv / specialties.csv), détection d'urgence

  Modules "service" (data/modules/*.jsonl) :
    - facturation_frais    : factures, frais de livraison/service/paiement, TVA, double débit
    - remboursement_avoir  : retours, remboursements, avoirs
    - securite_alerte_sms  : OTP, alertes SMS, phishing, double authentification
    - offres_fiabilite     : offres et packs du mois, mois gratuit, garanties
    - panne_acces_services : bugs (ajout panier, paiement...), statut des services
    - resiliation_contrat  : résiliation Premium, suppression de compte

Usage :
    python agent.py            # chat interactif
    python agent.py --debug    # affiche modules choisis, scores, documents retenus

Données attendues :
    data/mapara_in_stock.csv, data/mapara_out_of_stock.csv, data/diseases.csv, data/specialties.csv
    data/modules/01_facturation_frais.jsonl ... 06_resiliation_contrat.jsonl
"""
import argparse
import hashlib
import json
import os
import re
import sys
import threading
import time
import copy
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from backend.settings import ROOT

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()  # "gemini", "groq" ou "ollama"
GEN_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "qwen2.5:7b")  # modèle local du conseiller (supporte les appels d'outils)
OLLAMA_HOST = os.getenv("OLLAMA_HOST") or None
EMBED_BACKEND = os.getenv("EMBED_BACKEND", "local").lower()  # "local" (défaut) ou "gemini"
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
LOCAL_EMBED_MODEL = os.getenv("LOCAL_EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
EMBED_DIM = 768
EMBED_BATCH = int(os.getenv("EMBED_BATCH", "100"))
EMBED_SLEEP = float(os.getenv("EMBED_SLEEP", "2"))  # pause entre lots (quota gratuit)

DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
MODULES_DIR = Path(os.getenv("MODULES_DIR", str(DATA_DIR / "modules")))
CACHE_DIR = Path(os.getenv("CACHE_DIR", str(ROOT / ".cache")))
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", str(CACHE_DIR / "chroma")))  # dossier de la base vectorielle ChromaDB
TODAY = os.getenv("TODAY") or date.today().isoformat()  # AAAA-MM-JJ ; sert à détecter les offres expirées

K_IN_STOCK = 5          # candidats en stock envoyés au LLM
K_OUT_OF_STOCK = 3      # candidats en rupture envoyés au LLM
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.50" if EMBED_BACKEND == "gemini" else "0.35"))
MARGIN = float(os.getenv("MARGIN", "0.04"))  # écart pour dire "le + adapté est en rupture"
TOP_DISEASES = 8
TOP_SPECIALTIES = 6
HISTORY_TURNS = 6

# Modules "service" : nom -> (fichier jsonl, description donnée au routeur)
SERVICE_MODULES = {
    "facturation_frais": ("01_facturation_frais.jsonl",
                          "factures, frais de livraison / de service / de paiement, TVA, double débit, modes de paiement"),
    "remboursement_avoir": ("02_remboursement_avoir.jsonl",
                            "retours de produits, remboursements, avoirs (crédit boutique), produits défectueux ou ouverts"),
    "securite_alerte_sms": ("03_securite_alerte_sms.jsonl",
                            "sécurité du compte, codes OTP, alertes SMS, phishing / faux SMS, double authentification, données personnelles"),
    "offres_fiabilite": ("04_offres_fiabilite.jsonl",
                         "offres et packs du mois, promotions, mois gratuit, parrainage, fidélité, garanties, authenticité des produits"),
    "panne_acces_services": ("05_panne_acces_services.jsonl",
                             "bugs et pannes du site/appli : impossible d'ajouter au panier, paiement refusé, erreur, connexion impossible, statut des services"),
    "resiliation_contrat": ("06_resiliation_contrat.jsonl",
                            "résiliation d'abonnement Premium, suppression de compte, désabonnement, arrêt des prélèvements"),
    "conseil_paramedical": ("08_conseil_paramedical.jsonl",
                            "conseils parapharmacie pour un petit souci bénin (peau, cheveux, bouche, bébé, maman, fatigue, sommeil, digestion...), précautions (grossesse, enfant, allergies, compléments) et quand consulter pharmacien/médecin/urgences"),
    "guide_achat": ("09_guide_achat.jsonl",
                    "aide au choix d'un produit (type de peau, SPF, shampoing, routine), lecture d'étiquette, budget, produit en rupture, cadeaux, conservation"),
}
K_SERVICE_PER_MODULE = 8   # candidats par module
K_SERVICE = 8              # documents envoyés au LLM au total
MIN_SCORE_SERVICE = float(os.getenv("MIN_SCORE_SERVICE", "0.45" if EMBED_BACKEND == "gemini" else "0.30"))
EXAMPLE_TYPES = {"facture_exemple", "sms_exemple", "cas_exemple"}  # exemples fictifs : jamais les données du client

# --------------------------------------------------------------------------- #
# Client Gemini (créé à la demande)
# --------------------------------------------------------------------------- #
_client = None


def client():
    global _client
    if _client is None:
        from google import genai

        key = os.getenv("GEMINI_API_KEY")
        if not key:
            sys.exit("GEMINI_API_KEY manquante : copie .env.example vers .env et renseigne ta clé.")
        _client = genai.Client(api_key=key)
    return _client


_groq = None


def groq_client():
    global _groq
    if _groq is None:
        from groq import Groq

        key = os.getenv("GROQ_API_KEY")
        if not key:
            sys.exit("GROQ_API_KEY manquante : renseigne-la dans .env.")
        _groq = Groq(api_key=key)
    return _groq


class QuotaExhausted(RuntimeError):
    """Quota JOURNALIER épuisé pour un modèle : inutile de réessayer, on passe au modèle suivant."""


class ModelUnavailable(RuntimeError):
    """Modèle inexistant / retiré (404, decommissioned...) : inutile de réessayer."""


def _is_daily_quota(msg):
    m = msg.lower()
    return any(k in m for k in ("perday", "per day", "(tpd)", "(rpd)", "requests per day", "tokens per day"))


def _is_model_missing(msg):
    m = msg.lower()
    return any(k in m for k in ("404", "not found", "decommissioned", "does not exist",
                                "no longer supported", "model_not_found"))


def with_retry(fn, tries=3):
    """Réessaie seulement les erreurs passagères (429 par minute, 503, réseau)."""
    for attempt in range(tries):
        try:
            return fn()
        except Exception as e:  # quota 429, 503, réseau...
            msg = str(e)
            if _is_daily_quota(msg):
                raise QuotaExhausted(msg[:400]) from e
            if _is_model_missing(msg):
                raise ModelUnavailable(msg[:400]) from e
            if attempt == tries - 1:
                raise
            wait = min(5 * 2 ** attempt, 30)
            print(f"  [retry {attempt + 1}/{tries - 1}] {type(e).__name__}: attente {wait}s", file=sys.stderr)
            time.sleep(wait)


# --------------------------------------------------------------------------- #
_ollama = None


def ollama_client():
    global _ollama
    if _ollama is None:
        import ollama

        _ollama = ollama.Client(host=OLLAMA_HOST, timeout=int(os.getenv("OLLAMA_TIMEOUT", "180")))
    return _ollama


# Chaînes de modèles : "fournisseur:modèle" séparés par des virgules (voir .env)
#   LLM_CHAIN    : génération de la réponse finale
#   ROUTER_CHAIN : routeur + sélection de spécialité (petites tâches JSON) ; par défaut = LLM_CHAIN
# Exemple :
#   LLM_CHAIN=groq:openai/gpt-oss-120b,gemini:gemini-2.5-flash,groq:llama-3.1-8b-instant
#   ROUTER_CHAIN=groq:llama-3.1-8b-instant,gemini:gemini-2.5-flash-lite
# --------------------------------------------------------------------------- #
def _parse_chain(value, default):
    items = [x.strip() for x in (value or "").split(",") if x.strip()]
    items = [x for x in items if ":" in x and x.split(":", 1)[0] in ("groq", "gemini", "ollama")]
    return items or default


_DEFAULT_ENTRY = f"{LLM_PROVIDER}:{ {'groq': GROQ_MODEL, 'ollama': OLLAMA_LLM_MODEL}.get(LLM_PROVIDER, GEN_MODEL) }"
LLM_CHAIN = _parse_chain(os.getenv("LLM_CHAIN"), [_DEFAULT_ENTRY])
ROUTER_CHAIN = _parse_chain(os.getenv("ROUTER_CHAIN"), LLM_CHAIN)
QUOTA_PAUSE_S = int(os.getenv("QUOTA_PAUSE_S", "3600"))   # pause d'un modèle dont le quota du jour est épuisé
SOFT_PAUSE_S = int(os.getenv("SOFT_PAUSE_S", "60"))       # pause après une erreur passagère
AGENTIC = os.getenv("AGENTIC", "1") == "1"                       # 1 = Agentic Modular RAG ; 0 = ancien pipeline routeur
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "4"))          # nombre max de tours d'appels d'outils
AGENT_TEMPERATURE = float(os.getenv("AGENT_TEMPERATURE", "0.1"))  # basse : appels d'outils stables, réponse fidèle aux documents
LLM_CACHE = os.getenv("LLM_CACHE", "1") == "1"            # cache disque des appels déterministes (température 0)
# Longueur des réponses : le plafond est un filet de sécurité, la longueur visée (~110 mots) est dans le prompt.
# Sur gpt-oss les « tokens de raisonnement » comptent dans le plafond : d'où un plafond large + reasoning_effort bas.
ANSWER_MAX_TOKENS = int(os.getenv("ANSWER_MAX_TOKENS", "700"))    # max_completion_tokens (x2 pour les modèles non gpt-oss)
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "low")           # gpt-oss uniquement : low | medium | high ("" = défaut)


def _groq_limits(model, boost=1):
    """Paramètres de longueur envoyés à Groq (extra_body : valable quelle que soit la version du SDK)."""
    gpt_oss = "gpt-oss" in model
    body = {"max_completion_tokens": ANSWER_MAX_TOKENS * boost * (1 if gpt_oss else 2)}
    if gpt_oss and REASONING_EFFORT:
        body["reasoning_effort"] = REASONING_EFFORT
    return {"extra_body": body}


def clean_answer(text):
    """Filet de sécurité : réponse en un seul paragraphe, sans puces, titres, gras ni émojis de liste."""
    t = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    t = re.sub(r"[*`]+", "", t)
    t = re.sub(r"(?m)^\s*(?:#+|>)\s*", "", t)
    t = re.sub(r"[☀-➿⭐️⃣\U0001F300-\U0001FAFF]", "", t)
    lines = []
    for ln in t.splitlines():
        ln = re.sub(r"^\s*(?:[-•–]|\d+\s*[.)])\s+", "", ln).strip()
        if ln:
            lines.append(ln if re.search(r"[.!?:;…)]$", ln) else ln + ".")
    return re.sub(r"\s{2,}", " ", " ".join(lines)).strip()

_dead = {}         # "fournisseur:modèle" -> instant jusqu'auquel on le saute
LAST_MODEL = None  # dernier modèle ayant répondu (utile pour comparer RAG simple vs RAG + LoRA)
_llm_cache = None
_cache_lock = threading.Lock()
_CACHE_FILE = CACHE_DIR / "llm_cache.json"


def _cache_get(key):
    global _llm_cache
    with _cache_lock:
        if _llm_cache is None:
            try:
                _llm_cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            except Exception:
                _llm_cache = {}
        return _llm_cache.get(key)


def _cache_put(key, value):
    with _cache_lock:
        _llm_cache[key] = value
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            _CACHE_FILE.write_text(json.dumps(_llm_cache, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass


def _call(provider, model, prompt, system, json_mode, temperature, max_tokens=None):
    if provider == "ollama":
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        opts = {"temperature": temperature}
        if max_tokens:
            opts["num_predict"] = max_tokens
        r = with_retry(lambda: ollama_client().chat(model=model, messages=msgs, options=opts,
                                                    format="json" if json_mode else None))
        return re.sub(r"<think>.*?</think>", "", r["message"]["content"] or "", flags=re.S).strip()
    if provider == "groq":
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        kw = {"response_format": {"type": "json_object"}} if json_mode else {}
        if max_tokens:
            kw.update(_groq_limits(model))
        r = with_retry(lambda: groq_client().chat.completions.create(
            model=model, messages=msgs, temperature=temperature, **kw))
        return (r.choices[0].message.content or "").strip()

    from google.genai import types

    cfg = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        max_output_tokens=max_tokens or None,
        response_mime_type="application/json" if json_mode else None,
    )
    r = with_retry(lambda: client().models.generate_content(model=model, contents=prompt, config=cfg))
    return (r.text or "").strip()


def generate(prompt, system=None, json_mode=False, temperature=0.3, role="answer", max_tokens=None):
    """Appelle le premier modèle disponible de la chaîne ; bascule sur le suivant si quota / modèle indisponible."""
    global LAST_MODEL
    key = None
    if LLM_CACHE and temperature == 0:
        key = hashlib.sha256(json.dumps([role, system, prompt, json_mode], ensure_ascii=False).encode("utf-8")).hexdigest()
        hit = _cache_get(key)
        if hit:
            return hit

    chain = ROUTER_CHAIN if role == "router" else LLM_CHAIN
    errors = []
    for entry in chain:
        provider, model = entry.split(":", 1)
        env_key = {"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY"}.get(provider)
        if env_key and not os.getenv(env_key):
            errors.append(f"{entry} : clé {env_key} manquante")
            continue
        if _dead.get(entry, 0) > time.time():
            errors.append(f"{entry} : en pause (quota ou erreur récente)")
            continue
        try:
            out = _call(provider, model, prompt, system, json_mode, temperature, max_tokens)
        except QuotaExhausted as e:
            _dead[entry] = time.time() + QUOTA_PAUSE_S
            errors.append(f"{entry} : quota journalier épuisé")
            print(f"  [fallback] {entry} : quota JOURNALIER épuisé -> modèle suivant ({str(e)[:160]})", file=sys.stderr)
            continue
        except ModelUnavailable as e:
            _dead[entry] = float("inf")  # inutile de réessayer pendant cette session
            errors.append(f"{entry} : modèle indisponible")
            print(f"  [fallback] {entry} : modèle introuvable -> modèle suivant ({str(e)[:160]})", file=sys.stderr)
            continue
        except Exception as e:  # 429 par minute persistant, 503, réseau...
            _dead[entry] = time.time() + SOFT_PAUSE_S
            errors.append(f"{entry} : {type(e).__name__}")
            print(f"  [fallback] {entry} : {type(e).__name__}: {str(e)[:160]} -> modèle suivant", file=sys.stderr)
            continue
        LAST_MODEL = entry
        if key and out:
            _cache_put(key, out)
        return out

    raise RuntimeError("Aucun modèle LLM disponible pour le moment. Détails : " + " | ".join(errors) +
                       ". Ajoute d'autres modèles dans LLM_CHAIN (.env) ou réessaie plus tard.")


# --------------------------------------------------------------------------- #
# Embeddings (Gemini ou local) + base vectorielle ChromaDB
# --------------------------------------------------------------------------- #
def _normalize(a):
    a = np.asarray(a, dtype=np.float32)
    return a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)


_local_model = None


def _embed_raw(texts, task):
    """task: 'doc' ou 'query'."""
    if EMBED_BACKEND == "local":
        global _local_model
        if _local_model is None:
            from sentence_transformers import SentenceTransformer

            _local_model = SentenceTransformer(LOCAL_EMBED_MODEL)
        return _normalize(_local_model.encode(texts, batch_size=64, show_progress_bar=len(texts) > 200))

    from google.genai import types

    task_type = "RETRIEVAL_DOCUMENT" if task == "doc" else "RETRIEVAL_QUERY"
    cfg = types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBED_DIM)
    out = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i + EMBED_BATCH]
        r = with_retry(lambda: client().models.embed_content(model=GEMINI_EMBED_MODEL, contents=batch, config=cfg))
        out.extend(e.values for e in r.embeddings)
        if len(texts) > EMBED_BATCH:
            print(f"  embeddings {min(i + EMBED_BATCH, len(texts))}/{len(texts)}", file=sys.stderr)
            time.sleep(EMBED_SLEEP)
    return _normalize(out)


_chroma = None
_chroma_lock = threading.Lock()


def chroma_client():
    """Client ChromaDB persistant (créé à la demande)."""
    global _chroma
    with _chroma_lock:
        if _chroma is None:
            import chromadb
            from chromadb.config import Settings

            CHROMA_DIR.mkdir(parents=True, exist_ok=True)
            _chroma = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
        return _chroma


def index_collection(name, texts, metadatas=None):
    """Crée (ou recharge) la collection ChromaDB d'un index. L'identifiant d'un document = son numéro de ligne.

    Le nom de la collection contient un hash du contenu : si les textes ou les métadonnées changent, une nouvelle
    collection est construite et l'ancienne est supprimée. Reprise possible si l'indexation est interrompue."""
    backend = EMBED_BACKEND + ("-" + LOCAL_EMBED_MODEL if EMBED_BACKEND == "local" else "-" + GEMINI_EMBED_MODEL)
    key = hashlib.sha1((backend + "\n".join(texts) + json.dumps(metadatas, sort_keys=True, default=str)).encode()).hexdigest()[:12]
    cname = f"{name}__{key}"
    cl = chroma_client()
    for c in cl.list_collections():
        cn = c if isinstance(c, str) else c.name
        if cn.startswith(f"{name}__") and cn != cname:
            cl.delete_collection(cn)  # ancienne version de l'index
    col = cl.get_or_create_collection(cname, metadata={"hnsw:space": "cosine"})
    start = col.count()
    if start >= len(texts):
        return col
    print(f"Indexation '{name}' (ChromaDB) : {len(texts)} documents (reprise à {start})...", file=sys.stderr)
    chunk = EMBED_BATCH * 5
    for i in range(start, len(texts), chunk):
        part = texts[i:i + chunk]
        kw = {"metadatas": metadatas[i:i + chunk]} if metadatas else {}
        col.add(ids=[str(j) for j in range(i, i + len(part))],
                embeddings=_embed_raw(part, "doc").tolist(), documents=part, **kw)
    return col


def vs_query(col, qv, k, where=None):
    """Recherche dans ChromaDB. Retourne [(numéro_de_ligne, score_cosinus)] triés du plus au moins proche."""
    n = min(k, col.count())
    emb = [np.asarray(qv, dtype=np.float32).tolist()]
    while n > 0:
        try:
            r = col.query(query_embeddings=emb, n_results=n, where=where)
            return [(int(i), 1.0 - float(d)) for i, d in zip(r["ids"][0], r["distances"][0])]
        except Exception:
            if n == 1:
                return []
            n = max(1, n // 2)  # moins de résultats que demandé après filtrage
    return []


def embed_query(text):
    return _embed_raw([text], "query")[0]


# --------------------------------------------------------------------------- #
# Chargement des données
# --------------------------------------------------------------------------- #
def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def load_catalog():
    a = pd.read_csv(DATA_DIR / "mapara_in_stock.csv")
    b = pd.read_csv(DATA_DIR / "mapara_out_of_stock.csv")
    a["in_stock"] = True
    b["in_stock"] = False
    df = pd.concat([a, b], ignore_index=True)
    df = df.dropna(subset=["name", "url"])
    for c in ("brand", "categories", "description"):
        df[c] = df[c].fillna("").astype(str)
    df["name"] = df["name"].str.replace(r"\s*-\s*MaPara Tunisie\s*$", "", regex=True).str.strip()
    # un produit présent des deux côtés : on garde la version "en stock"
    df = df.sort_values("in_stock", ascending=False).drop_duplicates("url").reset_index(drop=True)
    return df


def product_doc(r):
    desc = re.sub(r"\s+", " ", r["description"])[:250]
    return f"{r['name']} | Marque : {r['brand']} | Catégories : {r['categories']} | {desc}"


RED_FLAGS = re.compile(
    r"(douleur (a|dans) la poitrine|douleur thoracique|oppression thoracique|difficulte a respirer|"
    r"du mal a respirer|essoufflement (soudain|brutal)|perte de connaissance|evanoui|malaise|convulsion|"
    r"visage qui tombe|paralysie|difficulte a parler|saignement abondant|vomi(t|ssement)? (du )?sang|"
    r"sang dans (les selles|les urines)|idees? suicidaires?|suicid|me faire du mal|envie de mourir|"
    r"gonflement (du visage|de la langue|de la gorge)|reaction allergique (grave|severe))"
)


def load_specialties():
    sp = pd.read_csv(DATA_DIR / "specialties.csv").fillna("")
    sp["doc"] = sp["specialty"] + ". Symptômes fréquents : " + sp["top_symptoms"].str.replace("|", ",", regex=False)
    return sp


def load_diseases(valid_specialties):
    d = pd.read_csv(DATA_DIR / "diseases.csv").fillna("")
    d["spec_list"] = d["specialties"].apply(
        lambda s: [x.strip() for x in s.split("|") if x.strip() in valid_specialties])
    d = d[d["spec_list"].map(len) > 0].reset_index(drop=True)
    d["doc"] = d["disease"] + ". Symptômes : " + d["symptoms"].str.replace("|", ",", regex=False)
    return d


# --------------------------------------------------------------------------- #
# Modules "service" : un index vectoriel par module
# --------------------------------------------------------------------------- #
class ServiceModule:
    """Un module = un fichier jsonl + son index vectoriel + sa recherche."""

    def __init__(self, name, path, description):
        self.name = name
        self.description = description
        self.docs = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.docs.append(json.loads(line))
        texts = [self.doc_text(d) for d in self.docs]
        metas = [{"is_example": d.get("type") in EXAMPLE_TYPES} for d in self.docs]
        self.col = index_collection(f"mod_{name}", texts, metas)

    @staticmethod
    def doc_text(d):
        kw = ", ".join(d.get("mots_cles", []))
        return f"{d.get('titre', '')}. {d.get('contenu', '')} Mots-clés : {kw}"

    def search(self, qv, k=K_SERVICE_PER_MODULE):
        """Top-k des documents de référence (politiques, FAQ, offres...) + au plus 2 exemples fictifs."""
        main = vs_query(self.col, qv, k, {"is_example": False})
        ex = vs_query(self.col, qv, 2, {"is_example": True})
        return [(sc, self.docs[i]) for i, sc in main + ex]


def find_module_file(filename):
    for base in (MODULES_DIR, DATA_DIR):
        p = base / filename
        if p.exists():
            return p
    return None


def format_service_doc(score, d):
    out = {
        "module": d.get("module"),
        "type": d.get("type"),
        "titre": d.get("titre"),
        "contenu": d.get("contenu"),
        "score": round(score, 3),
    }
    if d.get("type") in EXAMPLE_TYPES:
        out["illustratif"] = True  # exemple fictif, pas les données du client
    fin = d.get("fin")
    if fin:
        out["valable_jusqu_au"] = fin
        out["expire"] = fin < TODAY
    return out


# --------------------------------------------------------------------------- #
# Profil client + thématique (envoyés par le front)
# --------------------------------------------------------------------------- #
PROFILE_STYLES = {
    "calme": "Client calme : ton cordial et posé, réponse claire et complète.",
    "impatient": "Client impatient : va droit au but, réponse très courte, actions en premier, pas de détours.",
    "nerveux": "Client nerveux/anxieux : ton rassurant, phrases simples, explique que la situation se gère, étapes enchaînées (d'abord… ensuite…).",
    "mecontent": "Client mécontent : commence par reconnaître le désagrément avec empathie (une phrase), reste factuel, propose une solution concrète.",
    "fidele": "Client fidèle : ton chaleureux, remercie pour sa fidélité, mentionne les avantages utiles seulement s'ils figurent dans le contexte.",
    "confus": "Client confus : explique pas à pas avec des mots très simples, une idée par phrase, termine par une question de vérification.",
    "exigeant": "Client exigeant : réponse précise, chiffres/conditions exacts tels qu'écrits dans les documents, ton professionnel.",
}

# mot-clé (sans accent) trouvé dans la thématique -> module à forcer
TOPIC_KEYWORDS = [
    ("factur", "facturation_frais"), ("frais", "facturation_frais"), ("paiement", "facturation_frais"),
    ("rembours", "remboursement_avoir"), ("retour", "remboursement_avoir"), ("avoir", "remboursement_avoir"),
    ("secur", "securite_alerte_sms"), ("sms", "securite_alerte_sms"), ("otp", "securite_alerte_sms"),
    ("offre", "offres_fiabilite"), ("pack", "offres_fiabilite"), ("promo", "offres_fiabilite"),
    ("panne", "panne_acces_services"), ("bug", "panne_acces_services"), ("acces", "panne_acces_services"),
    ("resili", "resiliation_contrat"), ("abonn", "resiliation_contrat"),
    ("paramedic", "conseil_paramedical"), ("bien-etre", "conseil_paramedical"), ("precaution", "conseil_paramedical"),
    ("achat", "guide_achat"), ("choisir", "guide_achat"),
    ("produit", "product"), ("conseil", "product"),
    ("symptom", "symptom"), ("sante", "symptom"),
]


def fmt_history(history, n=None):
    """Historique pour le prompt : anciennes réponses tronquées, pour que le LLM ne re-réponde pas à l'ancienne question."""
    out = []
    for r, t in history[-(n or HISTORY_TURNS):]:
        t = re.sub(r"\s+", " ", str(t)).strip()
        if r != "Utilisateur" and len(t) > 280:
            t = t[:280].rsplit(" ", 1)[0] + " […]"
        out.append(f"{r}: {t}")
    return "\n".join(out)


def topic_modules(topic):
    """Modules à activer en priorité pour la thématique choisie dans le front."""
    if not topic:
        return []
    t = strip_accents(str(topic).lower())
    return list(dict.fromkeys(m for kw, m in TOPIC_KEYWORDS if kw in t))


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #
def build_router_system(active_services):
    svc = "\n".join(f'  - "{n}" : {SERVICE_MODULES[n][1]}' for n in active_services)
    names = ['"product"', '"symptom"'] + [f'"{n}"' for n in active_services]
    return f"""Tu es le routeur d'un assistant de parapharmacie en ligne (MaPara Tunisie). Analyse le dernier message de
l'utilisateur (en tenant compte de l'historique pour les questions de suivi) et choisis le ou les modules à activer.
Réponds UNIQUEMENT en JSON :
{{
 "modules": [{" | ".join(names)}, ...],
 "product_query": "requête de recherche produit en français : type de produit + type de peau/cheveux + problème (vide si module product absent)",
 "symptom_query": "symptômes reformulés en français médical simple, ex. 'douleur dentaire' (vide si module symptom absent)",
 "service_query": "demande de service reformulée en français avec mots-clés précis, ex. 'impossible ajouter produit panier' (vide si aucun module de service)",
 "urgent": true/false,
 "max_price_tnd": nombre ou null (budget maximum en dinars tunisiens si l'utilisateur en donne un, sinon null)
}}
Modules disponibles (plusieurs possibles dans le même message ; liste vide [] pour salutations, remerciements, hors-sujet) :
  - "product" : l'utilisateur cherche un produit de soin/hygiène/bien-être/complément alimentaire/bébé, etc.
  - "symptom" : l'utilisateur décrit des douleurs, symptômes ou un problème de santé.
{svc}
Règles :
- Choisis uniquement les modules réellement nécessaires (1 en général, 2-3 si le message mélange plusieurs demandes).
- Si une question peut relever de deux modules de service (ex. paiement bloqué : "facturation_frais" et "panne_acces_services"), active les deux.
- Une question sur un problème du site (ex. "je n'arrive pas à ajouter au panier") est un module de service, pas "product".
- Un problème de paiement (carte refusée, erreur au paiement, bouton qui ne répond pas) relève de "panne_acces_services" ; un montant, un débit
  ou une facture relève de "facturation_frais". En cas de doute sur un paiement, active les deux.
- Les mots "pack", "offre", "promo", "promotion", "mois gratuit" relèvent de "offres_fiabilite". Si le message demande aussi un type de produit
  ou de peau (ex. "un pack pour peau mixte"), active "product" ET "offres_fiabilite", et mets dans product_query uniquement le besoin
  (ex. "soin peau mixte à grasse"), sans les mots pack/offre/promo.
- Un petit souci bénin de peau, cheveux, bouche, bébé, maman ou bien-être (peau sèche, pellicules, fatigue, sommeil, érythème fessier...)
  relève de "conseil_paramedical" ET de "product" (mets le besoin dans product_query). Une question de précaution (grossesse,
  allaitement, enfant, allergie, compléments, "puis-je utiliser...", "quand consulter") relève de "conseil_paramedical".
  Un symptôme de santé inquiétant (fièvre, douleur forte, etc.) relève de "symptom" (et "conseil_paramedical" si besoin d'orientation).
- Une aide au choix ("comment choisir", type de peau, indice solaire, routine, budget, produit en rupture) relève de "guide_achat",
  avec "product" si le client veut des produits précis.
- "urgent" = true uniquement pour des signes de gravité (douleur thoracique, difficulté à respirer, perte de
  connaissance, paralysie, hémorragie, idées suicidaires, gonflement du visage/gorge...)."""


ANSWER_SYSTEM = """Tu es l'assistant conseil d'une parapharmacie en ligne tunisienne (MaPara Tunisie).
Réponds dans la langue de l'utilisateur (français par défaut), ton chaleureux, clair et concis.
Si le message contient plusieurs demandes, traite chacune dans l'ordre, brièvement.
Ne commence pas par « Bonjour » sauf si HISTORIQUE est vide.

FORMAT DE LA RÉPONSE (obligatoire)
- UN SEUL PARAGRAPHE rédigé, comme un conseiller qui parle au téléphone : phrases enchaînées, sans retour à la ligne.
- Aucune liste, aucune puce, aucun numéro, aucun titre, aucun gras, aucun tableau, aucun émoji.
- Longueur : 3 à 5 phrases, 110 mots maximum (60 mots pour un client impatient). Va à l'essentiel, ne répète pas la question.
- Ordre des idées : une courte phrase d'accueil ou d'empathie, puis la réponse ou le conseil principal, puis (si utile) le produit avec
  son prix et son lien intégrés dans la phrase, puis la précaution ou le « consulter si… » en une phrase, et enfin au plus UNE question.
- Plusieurs étapes se disent avec « d'abord… ensuite… enfin… » dans la même phrase, jamais en liste.

RÈGLES GÉNÉRALES
- Utilise UNIQUEMENT les produits fournis dans CONTEXTE_PRODUITS. N'invente jamais de produit, de prix, de lien ni de composition.
- Ne pose pas de diagnostic et ne recommande aucun médicament ni dosage.
- Les prix sont en dinars tunisiens : écris-les EXACTEMENT comme fournis dans le champ "prix" (ex. « 68,10 DT »). N'utilise JAMAIS le symbole € ni le mot euro, ne convertis rien.

BRANCHE PRODUIT (scénario fourni dans CONTEXTE_PRODUITS.scenario)
PRIORITÉ ABSOLUE : les produits EN STOCK passent toujours en premier.
- "in_stock" : recommande 1 ou 2 produits EN STOCK (3 seulement si le client en demande plusieurs), du plus adapté au moins adapté. Pour chacun :
  nom, marque, prix (champ "prix"), en une demi-phrase pourquoi il convient, et le lien pour commander. Indique qu'il est disponible.
  Si "produits_en_rupture" n'est pas vide, ajoute à la FIN une seule phrase courte du type
  « À noter : [nom] est actuellement en rupture de stock. » Ne le présente JAMAIS comme le meilleur choix et ne mets pas son lien en avant.
- "only_out_of_stock" : dis clairement qu'aucun produit adapté n'est disponible en stock pour le moment (en rappelant le budget
  s'il y en a un), puis cite le produit en rupture comme simple piste, sans inciter à commander.
- "no_match" : dis honnêtement que tu n'as pas trouvé de produit adapté dans le catalogue (dans la limite du budget si fourni)
  et propose de reformuler.
- Si "budget_max_tnd" est fourni, ne recommande aucun produit au-dessus de ce prix.
- Ne recommande un produit que si sa catégorie ou sa description correspond clairement au besoin exprimé (ex. n'écris pas qu'une huile
  ou un soin du corps convient à un nettoyant visage). N'attribue à un produit aucune propriété absente de sa description. Si aucun
  produit ne correspond vraiment, dis-le honnêtement au lieu de remplir la liste.
- Si une information utile manque (type de peau, âge, allergies...), donne quand même une recommandation puis pose UNE seule question.
- Pour les produits de soin, rappelle en une phrase de lire la notice/faire un test sur une petite zone si peau sensible.

BRANCHE SYMPTÔMES (CONTEXTE_MEDICAL)
- Recommande de consulter le(s) spécialiste(s) listé(s) (le premier en priorité) ; les noms sont des spécialités médicales :
  traduis-les en praticien courant (ex. une spécialité en « -logie » -> « médecin spécialiste en ... »), explique en une ou deux phrases pourquoi.
- Ne cite pas de maladies et ne rassure pas à tort ; précise que seul un professionnel de santé peut poser un diagnostic.
- Si "urgent" est vrai : commence par dire d'appeler immédiatement les urgences (190, SAMU en Tunisie) ou de se rendre aux urgences.
- Ne propose pas de produits pour traiter le symptôme ; tu peux seulement proposer, à la fin, un produit d'hygiène/confort
  clairement fourni dans CONTEXTE_PRODUITS s'il y en a un, en précisant qu'il ne remplace pas la consultation.

BRANCHE SERVICE (CONTEXTE_SERVICE : facturation, remboursement, sécurité, offres, pannes, résiliation)
- Réponds UNIQUEMENT à partir des documents de CONTEXTE_SERVICE. N'invente aucun nom de menu, de bouton, d'option ou d'étape
  qui n'est pas écrit dans les documents (ex. n'écris pas « Mes avoirs » ou « Utiliser un avoir » s'ils n'apparaissent pas) : si les
  documents ne décrivent pas la procédure demandée, dis-le et invite à contacter le support. Reprends les conditions, délais et
  montants tels qu'ils sont écrits, sans les reformuler ni les extrapoler (pas de calcul, pas de « à compter de », pas de « sans restriction »
  si ce n'est pas écrit). Ne décris une étape de navigation (page, bouton, case) que si elle figure dans les documents. N'invente aucun frais, délai, code promo, numéro de téléphone
  ou règle absent des documents. Écris les montants de ces documents en « DT » (jamais en euros).
- Si les documents ne répondent pas directement à la question posée (même s'ils traitent d'un sujet proche), dis-le d'abord et ne comble
  pas le vide : renvoie au support. Ne transforme pas un document sur un autre cas (ex. double débit) en réponse à la question.
- Les documents avec "illustratif": true (factures, SMS, cas d'exemple) sont des exemples fictifs : ne les présente JAMAIS comme
  les données du client ; sers-t'en uniquement pour illustrer une règle.
- Les documents avec "expire": true sont des offres terminées : ne les propose pas, dis qu'elles sont terminées. Pour les offres/packs
  valides, donne nom, contenu, prix/remise et date de fin.
- Documents de type "statut_service" : indique l'état du service ; si « dégradé » ou « incident majeur », donne la durée estimée ;
  sinon propose les étapes de dépannage.
- Tu n'as PAS accès au compte, aux commandes ni aux paiements du client : explique la procédure étape par étape et ne prétends
  jamais avoir effectué une action (remboursement, résiliation, déblocage de compte, annulation).
- Sécurité : ne demande jamais de mot de passe, de code OTP ni de numéro de carte. Ne rappelle de ne pas les communiquer que si la
  question concerne la sécurité, un paiement ou un SMS suspect (pas dans les autres réponses).
- Si "scenario" vaut "no_match" : dis honnêtement que tu n'as pas l'information et invite à contacter le support client du site.
- Si le service concerne un bug d'ajout au panier et que le contexte le permet, mentionne aussi la cause possible « produit en rupture ».

CONSEIL PARAMÉDICAL ET GUIDE D'ACHAT (documents des modules "conseil_paramedical" et "guide_achat" dans CONTEXTE_SERVICE)
- Appuie-toi sur ces documents pour donner des gestes simples, des précautions et des critères de choix. Tu peux expliquer ce qu'ils contiennent
  avec tes mots, sans rien ajouter de médical qui n'y figure pas (pas de maladie nommée, pas de dosage, pas de médicament).
- Les produits proposés viennent UNIQUEMENT de CONTEXTE_PRODUITS ; les « rayons du catalogue » cités dans les documents sont des pistes de
  recherche, jamais des produits à citer s'ils ne sont pas dans CONTEXTE_PRODUITS.
- Termine par UNE phrase reprenant le « consulter si… » du document quand il y en a (pharmacien, médecin, dentiste, dermatologue). Si la personne est
  enceinte, allaitante, très jeune, âgée, allergique ou sous traitement, rappelle la précaution correspondante.
- Signes de gravité : commence par dire d'appeler les urgences (190, SAMU). Ne conseille aucun médicament : renvoie vers un pharmacien.
"""

ANSWER_SYSTEM += """
PROFIL CLIENT ET THÉMATIQUE (CONTEXTE_CLIENT)
- "consigne_ton" décrit comment adapter le TON, la LONGUEUR et la STRUCTURE de la réponse au profil du client ; "thematique" est le sujet de la demande.
- N'écris jamais le mot « profil » ni le type de client (ex. « vous êtes impatient ») dans la réponse.
- Ces consignes changent uniquement la forme : les règles sur les faits, prix, procédures et sécurité restent inchangées.
"""


SPECIALTY_SELECTOR_SYSTEM = """Tu choisis la ou les spécialités médicales à consulter pour des symptômes décrits par un patient.
Tu reçois :
- SYMPTOMES : ce que décrit le patient ;
- LISTE_SPECIALITES : la liste complète des spécialités autorisées (issue de la base de données) ;
- PISTES : spécialités et maladies les plus proches des symptômes, issues de la base (indices, parfois bruités) ;
- SPECIALITES_PROCHES : spécialités dont les symptômes typiques ressemblent à ceux du patient.
Règles :
- Choisis UNIQUEMENT des valeurs présentes à l'identique dans LISTE_SPECIALITES.
- Compare les symptômes avec les PISTES et SPECIALITES_PROCHES, mais garde le bon sens médical : la spécialité doit concerner
  la partie du corps / le problème décrit. Écarte les entrées qui ne correspondent pas à la consultation d'un patient humain.
- 1 à 3 spécialités, de la plus pertinente à la moins pertinente.
Réponds UNIQUEMENT en JSON : {"specialties": ["..."]}"""


# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #
AGENT_SYSTEM = ANSWER_SYSTEM + """
MODE AGENT : OUTILS DE RECHERCHE
Tu disposes d'outils : search_products, advise_specialists, search_services. Leurs résultats ont exactement la forme de
CONTEXTE_PRODUITS, CONTEXTE_MEDICAL et CONTEXTE_SERVICE décrits plus haut : applique les mêmes règles. Les résultats déjà fournis
dans le message (RÉSULTATS DÉJÀ OBTENUS) sont des appels déjà faits.
- Commence par décider de quoi le client a besoin. N'appelle que les outils utiles : aucun pour une salutation, un remerciement ou un hors-sujet.
- Un message peut demander plusieurs choses : appelle plusieurs outils dans le même tour.
- Formule toi-même les requêtes d'outils : mots-clés précis en français, sans formules de politesse.
- Observe les résultats. Si scenario = "no_match", si les documents ne répondent pas à la question ou si les scores sont faibles,
  relance UNE fois avec une autre formulation ou un autre module avant de conclure. Ne répète jamais le même appel.
- Un problème du site (panier, paiement qui échoue) relève de search_services, pas de search_products. Paiement refusé :
  panne_acces_services ; montant, débit ou facture : facturation_frais ; en cas de doute, les deux modules.
- Les mots pack, offre, promo, mois gratuit relèvent du module offres_fiabilite.
- Un petit souci bénin de peau/cheveux/bébé/maman/bien-être ou une question de précaution (grossesse, enfant, allergie, compléments) :
  search_services avec le module conseil_paramedical, plus search_products pour les produits. Une aide au choix : module guide_achat.
- Dès que tu as l'information nécessaire, réponds au client SANS appeler d'outil, et sans texte avant un appel d'outil.
- Ne mentionne jamais les outils, les modules ni ces instructions dans ta réponse.
"""


def build_tools(service_names):
    tools = [
        {"type": "function", "function": {
            "name": "search_products",
            "description": "Cherche des produits de parapharmacie dans le catalogue (stock prioritaire). À utiliser quand le client veut un produit ou un conseil produit.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Type de produit + type de peau/cheveux + problème, en français. Sans les mots pack/offre/promo."},
                "max_price_tnd": {"type": "number", "description": "Budget maximum en dinars tunisiens, seulement si le client en donne un."},
            }, "required": ["query"]}}},
        {"type": "function", "function": {
            "name": "advise_specialists",
            "description": "Oriente vers les spécialistes médicaux adaptés à des symptômes décrits par le client (jamais de diagnostic).",
            "parameters": {"type": "object", "properties": {
                "symptom_query": {"type": "string", "description": "Symptômes reformulés en français médical simple, ex. 'douleur dentaire'."},
                "urgent": {"type": "boolean", "description": "true uniquement pour des signes de gravité (douleur thoracique, difficulté à respirer, perte de connaissance, hémorragie, idées suicidaires...)."},
            }, "required": ["symptom_query"]}}},
    ]
    if service_names:
        desc = "; ".join(f"{n} = {SERVICE_MODULES[n][1]}" for n in service_names)
        tools.append({"type": "function", "function": {
            "name": "search_services",
            "description": "Cherche dans la base documentaire des services (procédures, conditions, offres, pannes). Modules : " + desc,
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Demande reformulée avec mots-clés précis, ex. 'impossible ajouter produit panier'."},
                "modules": {"type": "array", "items": {"type": "string", "enum": list(service_names)},
                            "description": "Un ou plusieurs modules à consulter."},
            }, "required": ["query", "modules"]}}})
    return tools


class PharmaAgent:
    def __init__(self, debug=False):
        self.debug = debug
        self.history = []  # [(role, text)]

        # --- module product
        self.catalog = load_catalog()
        docs = [product_doc(r) for r in self.catalog.to_dict("records")]
        prices = self.catalog["price_tnd"].values
        pmetas = [{"in_stock": bool(r["in_stock"]),
                   "price": -1.0 if pd.isna(prices[i]) else float(prices[i])}  # -1 = prix non indiqué
                  for i, r in enumerate(self.catalog.to_dict("records"))]
        self.pcol = index_collection("products", docs, pmetas)
        self.in_idx = np.where(self.catalog["in_stock"].values)[0]
        self.out_idx = np.where(~self.catalog["in_stock"].values)[0]

        # --- module symptom
        self.specialties = load_specialties()
        self.valid_specialties = set(self.specialties["specialty"])
        self.scol = index_collection("specialties", self.specialties["doc"].tolist())
        self.diseases = load_diseases(self.valid_specialties)
        self.dcol = index_collection("diseases", self.diseases["doc"].tolist())

        # --- modules service
        self.services = {}
        for name, (filename, desc) in SERVICE_MODULES.items():
            path = find_module_file(filename)
            if path is None:
                print(f"  [attention] module '{name}' ignoré : {filename} introuvable dans {MODULES_DIR}",
                      file=sys.stderr)
                continue
            self.services[name] = ServiceModule(name, path, desc)
        self.router_system = build_router_system(list(self.services))
        self.valid_modules = {"product", "symptom"} | set(self.services)
        self.tools = build_tools(list(self.services))

        print(f"Catalogue : {len(self.in_idx)} en stock, {len(self.out_idx)} en rupture | "
              f"{len(self.diseases)} maladies indexées | modules service : "
              f"{', '.join(f'{n} ({len(m.docs)})' for n, m in self.services.items()) or 'aucun'}.", file=sys.stderr)

    # ---- routage ---------------------------------------------------------- #
    def route(self, message, history):
        hist = "\n".join(f"{r}: {t}" for r, t in history[-HISTORY_TURNS:])
        prompt = f"HISTORIQUE:\n{hist or '(vide)'}\n\nDERNIER MESSAGE:\n{message}"
        try:
            data = json.loads(generate(prompt, system=self.router_system, json_mode=True, temperature=0, role="router"))
        except Exception as e:
            print(f"  [attention] routeur indisponible ({type(e).__name__}) -> routage par défaut 'product'", file=sys.stderr)
            data = {"modules": ["product"], "product_query": message, "symptom_query": "", "service_query": "",
                    "urgent": False, "max_price_tnd": None}
        mods = data.get("modules")
        if not isinstance(mods, list):
            mods = []
        data["modules"] = [m for m in dict.fromkeys(mods) if m in self.valid_modules]  # dédoublonné, validé
        data["intent"] = self.intent_label(data["modules"])
        try:
            mp = data.get("max_price_tnd")
            data["max_price_tnd"] = float(mp) if mp is not None else None
        except (TypeError, ValueError):
            data["max_price_tnd"] = None
        data["urgent"] = bool(data.get("urgent")) or bool(RED_FLAGS.search(strip_accents(message.lower())))
        return data

    @staticmethod
    def intent_label(modules):
        """Étiquette compatible avec l'ancienne version (product / symptom / both / chitchat)."""
        s = set(modules)
        if not s:
            return "chitchat"
        if s == {"product"}:
            return "product"
        if s == {"symptom"}:
            return "symptom"
        if s == {"product", "symptom"}:
            return "both"
        if not (s & {"product", "symptom"}):
            return "service"
        return "multi"

    # ---- module product -------------------------------------------------- #
    def search_products(self, query, max_price=None):
        """Le stock est TOUJOURS prioritaire ; la rupture n'est qu'une info secondaire."""
        qv = embed_query(query)

        def top(in_stock, k):
            conds = [{"in_stock": in_stock}]
            if max_price is not None:  # budget : on garde aussi les produits sans prix indiqué (price = -1)
                conds.append({"$or": [{"price": {"$lte": float(max_price)}}, {"price": {"$lt": 0}}]})
            return vs_query(self.pcol, qv, k, conds[0] if len(conds) == 1 else {"$and": conds})

        top_in, top_out = top(True, K_IN_STOCK), top(False, K_OUT_OF_STOCK)
        s = dict(top_in + top_out)  # numéro de ligne -> score cosinus

        in_list = [i for i, sc in top_in if sc >= MIN_SCORE]
        out_list = [i for i, sc in top_out if sc >= MIN_SCORE]

        if in_list:
            scenario = "in_stock"  # on recommande le stock, point.
            # on ne signale une rupture que si elle est nettement plus adaptée (simple note)
            out_list = out_list[:1] if out_list and s[out_list[0]] - s[in_list[0]] >= MARGIN else []
        elif out_list:
            scenario = "only_out_of_stock"  # rien d'adapté en stock
        else:
            scenario = "no_match"

        def fmt(i):
            r = self.catalog.iloc[i]
            price = r["price_tnd"]
            return {
                "nom": r["name"], "marque": r["brand"], "categories": r["categories"],
                "prix": "prix non indiqué" if pd.isna(price) else f"{float(price):.2f} DT".replace(".", ","),
                "en_stock": bool(r["in_stock"]), "lien": r["url"],
                "description": re.sub(r"\s+", " ", r["description"])[:300],
                "score": round(float(s[i]), 3),
            }

        return {
            "scenario": scenario,
            "budget_max_tnd": max_price,
            "produits_en_stock": [fmt(i) for i in in_list],
            "produits_en_rupture": [fmt(i) for i in out_list],
        }

    # ---- module symptom -------------------------------------------------- #
    def advise_specialists(self, symptom_query, raw_message):
        qv = embed_query(symptom_query)

        # 1) maladies proches (diseases.csv) -> spécialités associées
        scores = defaultdict(float)
        pistes = []
        for i, sc in vs_query(self.dcol, qv, TOP_DISEASES):
            row = self.diseases.iloc[i]
            for sp in row["spec_list"]:
                scores[sp] += max(sc, 0.0)
            pistes.append({"maladie": row["disease"], "symptomes": row["symptoms"],
                           "specialites": row["spec_list"]})

        # 2) spécialités proches (specialties.csv)
        top_s = vs_query(self.scol, qv, TOP_SPECIALTIES)
        proches = [{"specialite": self.specialties.iloc[i]["specialty"],
                    "symptomes_typiques": self.specialties.iloc[i]["top_symptoms"]} for i, _ in top_s]
        for i, sc in top_s:
            scores[self.specialties.iloc[i]["specialty"]] += max(sc, 0.0)

        fallback = [sp for sp, _ in sorted(scores.items(), key=lambda kv: -kv[1])[:3]]

        # 3) Gemini compare les symptômes aux données et choisit dans la liste issue du CSV
        prompt = json.dumps({
            "SYMPTOMES": f"{symptom_query} (message du patient : {raw_message})",
            "LISTE_SPECIALITES": sorted(self.valid_specialties),
            "PISTES": pistes,
            "SPECIALITES_PROCHES": proches,
        }, ensure_ascii=False)
        chosen = []
        try:
            data = json.loads(generate(prompt, system=SPECIALTY_SELECTOR_SYSTEM, json_mode=True, temperature=0, role="router"))
            chosen = [x for x in data.get("specialties", []) if x in self.valid_specialties][:3]
        except Exception as e:
            print(f"  [attention] sélection de spécialité indisponible ({type(e).__name__}) -> repli sur les scores", file=sys.stderr)
        specialists = chosen or fallback or ["médecine générale"]
        return {"specialistes_recommandes": specialists,
                "_debug": {"choisies": chosen, "fallback": fallback, "pistes": [p["maladie"] for p in pistes[:5]]}}

    # ---- modules service ------------------------------------------------- #
    def search_services(self, query, module_names):
        """Recherche dans les index des modules choisis ; élargie à tous les modules si rien de pertinent."""
        qv = embed_query(query)

        def collect(names):
            hits = []
            for n in names:
                hits += self.services[n].search(qv)
            hits = sorted((h for h in hits if h[0] >= MIN_SCORE_SERVICE), key=lambda h: -h[0])
            main = [h for h in hits if h[1].get("type") not in EXAMPLE_TYPES]
            ex = [h for h in hits if h[1].get("type") in EXAMPLE_TYPES]
            return (main + ex[:max(0, 2 - len(main))])[:K_SERVICE]

        hits = collect(module_names)
        # secours inter-modules : un document d'un autre module meilleur que tout ce qui a été trouvé est ajouté (max 2)
        others = [n for n in self.services if n not in module_names]
        best = hits[0][0] if hits else 0.0
        extra = [h for h in (collect(others) if others else []) if h[0] > best][:2]
        consulted = list(module_names) + sorted({h[1].get("module") for h in extra} - set(module_names))
        hits = sorted(hits + extra, key=lambda h: -h[0])[:K_SERVICE]
        widened = False
        if not hits and set(module_names) != set(self.services):
            hits = collect(list(self.services))  # filet de sécurité si le routeur s'est trompé de module
            widened = bool(hits)
        return {
            "scenario": "found" if hits else "no_match",
            "date_du_jour": TODAY,
            "modules_consultes": consulted if not widened else list(self.services),
            "documents": [format_service_doc(sc, d) for sc, d in hits],
        }

    # ---- orchestration --------------------------------------------------- #
    def ask(self, message, history=None):
        return self.chat(message, history)["answer"]

    def chat_pipeline(self, message, history=None, profile=None, topic=None, rag=True):
        """Ancien mode : routeur LLM -> recherche -> réponse (sans boucle d'outils). Sert aussi de repli.
        history : liste [(role, texte)] propre à la session (par défaut l'historique du CLI)."""
        history = self.history if history is None else history
        route = self.route(message, history)
        modules = route["modules"]
        context = {}

        # la thématique choisie par l'utilisateur est prioritaire sur le routeur
        # la thématique ne s'impose qu'au 1er tour : ensuite c'est la question du client qui décide
        topic_first = topic if not history else None
        forced = [m for m in topic_modules(topic_first) if m in self.valid_modules]
        if forced:
            modules = list(dict.fromkeys(forced + modules))
            route["modules"] = modules
            route["intent"] = self.intent_label(modules)
            if "product" in forced and not route.get("product_query"):
                route["product_query"] = message
            if "symptom" in forced and not route.get("symptom_query"):
                route["symptom_query"] = message
        if not rag:  # RAG désactivé : aucune recherche documentaire
            modules = []

        if "product" in modules and route.get("product_query"):
            context["CONTEXTE_PRODUITS"] = self.search_products(route["product_query"], route.get("max_price_tnd"))
        if "symptom" in modules and route.get("symptom_query"):
            med = self.advise_specialists(route["symptom_query"], message)
            context["CONTEXTE_MEDICAL"] = {
                "urgent": route["urgent"],
                "specialistes_recommandes": med["specialistes_recommandes"],
            }
            if self.debug:
                context["_debug_specialites"] = med["_debug"]
        elif route["urgent"]:
            context["CONTEXTE_MEDICAL"] = {"urgent": True, "specialistes_recommandes": ["médecin généraliste"]}

        service_mods = [m for m in modules if m in self.services]
        if service_mods:
            context["CONTEXTE_SERVICE"] = self.search_services(route.get("service_query") or message, service_mods)

        if self.debug:
            print(f"[debug] route={route}", file=sys.stderr)
            for k, v in context.items():
                print(f"[debug] {k}={json.dumps(v, ensure_ascii=False, default=str)[:1500]}", file=sys.stderr)

        hist = fmt_history(history)
        payload = {k: v for k, v in context.items() if not k.startswith("_")}
        client_ctx = ""
        if profile or topic_first:
            client_ctx = "CONTEXTE_CLIENT:\n" + json.dumps(
                {"profil": profile, "consigne_ton": PROFILE_STYLES.get(profile or "", ""), "thematique": topic_first},
                ensure_ascii=False) + "\n\n"
        prompt = (
            f"HISTORIQUE (contexte seulement, ne réponds plus aux anciens messages) :\n{hist or '(vide)'}\n\n"
            f"MESSAGE UTILISATEUR À TRAITER MAINTENANT (réponds uniquement à celui-ci) :\n{message}\n\n{client_ctx}"
            f"{json.dumps(payload, ensure_ascii=False, indent=1) if payload else '(aucun contexte : réponds brièvement et propose ton aide pour un conseil produit, des symptômes ou une question sur une commande, un paiement, une offre ou ton compte)'}"
        )
        # réponses de service : température basse pour coller aux documents (pas d'invention de procédure)
        answer = generate(prompt, system=ANSWER_SYSTEM, temperature=0.1 if "CONTEXTE_SERVICE" in payload else 0.3,
                          max_tokens=ANSWER_MAX_TOKENS)
        answer = clean_answer(answer)
        answer = re.sub(r"\s*(€|\beuros?\b|\bEUR\b)", " DT", answer, flags=re.IGNORECASE)  # sécurité : jamais d'euro
        history += [("Utilisateur", message), ("Assistant", answer)]
        return {"answer": answer, "intent": route["intent"], "modules": modules,
                "urgent": route["urgent"], "profile": profile, "topic": topic, "context": payload,
                "model": LAST_MODEL, "mode": "pipeline", "steps": []}

    # ---- mode AGENT : le LLM choisit et enchaîne les outils ---------------- #
    @staticmethod
    def _merge_products(ctx, res):
        old = ctx.get("CONTEXTE_PRODUITS")
        if not old:
            ctx["CONTEXTE_PRODUITS"] = res
            return

        def mg(a, b):
            d = {p["lien"]: p for p in a}
            d.update({p["lien"]: p for p in b})
            return sorted(d.values(), key=lambda p: -p["score"])

        ins = mg(old["produits_en_stock"], res["produits_en_stock"])[:K_IN_STOCK * 2]
        links = {p["lien"] for p in ins}
        outs = [p for p in mg(old["produits_en_rupture"], res["produits_en_rupture"]) if p["lien"] not in links][:K_OUT_OF_STOCK]
        ctx["CONTEXTE_PRODUITS"] = {
            "scenario": "in_stock" if ins else ("only_out_of_stock" if outs else "no_match"),
            "budget_max_tnd": res.get("budget_max_tnd", old.get("budget_max_tnd")),
            "produits_en_stock": ins, "produits_en_rupture": outs}

    @staticmethod
    def _merge_services(ctx, res):
        old = ctx.get("CONTEXTE_SERVICE")
        if not old:
            ctx["CONTEXTE_SERVICE"] = res
            return
        docs = {(d.get("module"), d.get("titre")): d for d in old["documents"]}
        for d in res["documents"]:
            k = (d.get("module"), d.get("titre"))
            if k not in docs or d["score"] > docs[k]["score"]:
                docs[k] = d
        docs = sorted(docs.values(), key=lambda d: -d["score"])[:K_SERVICE * 2]
        ctx["CONTEXTE_SERVICE"] = {
            "scenario": "found" if docs else "no_match", "date_du_jour": TODAY,
            "modules_consultes": list(dict.fromkeys(old["modules_consultes"] + res["modules_consultes"])),
            "documents": docs}

    @staticmethod
    def _merge_medical(ctx, specialists, urgent):
        old = ctx.get("CONTEXTE_MEDICAL") or {}
        prev = [x for x in old.get("specialistes_recommandes", []) if x != "médecin généraliste"]
        ctx["CONTEXTE_MEDICAL"] = {
            "urgent": bool(old.get("urgent")) or bool(urgent),
            "specialistes_recommandes": list(dict.fromkeys(prev + list(specialists))) or ["médecin généraliste"]}

    def _run_tool(self, name, args, message, ctx, steps, source="agent"):
        """Exécute un outil, met à jour le contexte accumulé et trace l'étape. Retourne l'observation donnée au LLM."""
        t0 = time.perf_counter()
        modules = []
        try:
            if name == "search_products":
                q = str(args.get("query") or message)
                try:
                    mp = float(args["max_price_tnd"]) if args.get("max_price_tnd") is not None else None
                except (TypeError, ValueError):
                    mp = None
                res = self.search_products(q, mp)
                self._merge_products(ctx, res)
                obs = {"CONTEXTE_PRODUITS": res}
                summ = f"{res['scenario']} : {len(res['produits_en_stock'])} en stock, {len(res['produits_en_rupture'])} en rupture"
                modules = ["product"]
            elif name == "advise_specialists":
                q = str(args.get("symptom_query") or message)
                med = self.advise_specialists(q, message)
                self._merge_medical(ctx, med["specialistes_recommandes"], args.get("urgent"))
                obs = {"CONTEXTE_MEDICAL": ctx["CONTEXTE_MEDICAL"]}
                summ = "spécialistes : " + ", ".join(med["specialistes_recommandes"])
                modules = ["symptom"]
            elif name == "search_services" and self.services:
                q = str(args.get("query") or message)
                mods = args.get("modules") or []
                mods = [m for m in (mods if isinstance(mods, list) else [mods]) if m in self.services] or list(self.services)
                res = self.search_services(q, mods)
                self._merge_services(ctx, res)
                obs = {"CONTEXTE_SERVICE": res}
                best = max((d["score"] for d in res["documents"]), default=0.0)
                summ = f"{res['scenario']} : {len(res['documents'])} documents (meilleur score {best:.2f})"
                modules = mods
            else:
                obs, summ = {"erreur": f"outil inconnu : {name}"}, "outil inconnu"
        except Exception as e:
            obs, summ = {"erreur": str(e)[:200]}, f"erreur : {type(e).__name__}"
        steps.append({"step": len(steps) + 1, "tool": name, "args": args, "observation": summ, "modules": modules,
                      "source": source, "ms": int((time.perf_counter() - t0) * 1000)})
        return obs

    @staticmethod
    def _agent_round(provider, model, messages, tools, last, boost=1):
        """Un tour de LLM avec outils -> (texte, appels[(id, nom, arguments dict)], coupé_par_plafond)."""
        if provider == "ollama":
            r = with_retry(lambda: ollama_client().chat(
                model=model, messages=messages, tools=None if last else tools,
                options={"temperature": AGENT_TEMPERATURE, "num_predict": ANSWER_MAX_TOKENS * boost}), tries=2)
            m = r["message"]
            calls = [(f"call_{i}", c["function"]["name"], dict(c["function"]["arguments"] or {}))
                     for i, c in enumerate(m.get("tool_calls") or [])]
            return re.sub(r"<think>.*?</think>", "", m.get("content") or "", flags=re.S).strip(), calls, False
        r = with_retry(lambda: groq_client().chat.completions.create(
            model=model, messages=messages, tools=tools, tool_choice="none" if last else "auto",
            temperature=AGENT_TEMPERATURE, **_groq_limits(model, boost=boost)), tries=2)
        msg = r.choices[0].message
        calls = []
        for c in msg.tool_calls or []:
            try:
                args = json.loads(c.function.arguments or "{}")
            except Exception:
                args = {}
            calls.append((c.id, c.function.name, args if isinstance(args, dict) else {}))
        return (msg.content or "").strip(), calls, r.choices[0].finish_reason == "length"

    def _agent_loop(self, provider, model, messages, ctx, steps, message):
        """Boucle ReAct : le LLM appelle des outils, observe, puis répond. Dernier tour : outils interdits."""
        seen = set()
        for rnd in range(AGENT_MAX_STEPS + 1):
            last = rnd == AGENT_MAX_STEPS
            text, calls, cut = self._agent_round(provider, model, messages, self.tools, last)
            if cut and not calls and not text:
                # plafond atteint pendant le raisonnement : un seul nouvel essai avec un plafond doublé
                text, calls, _ = self._agent_round(provider, model, messages, self.tools, True, boost=2)
            if last or not calls:
                return text
            messages.append({"role": "assistant", "content": text, "tool_calls": [
                {"id": cid, "type": "function",
                 "function": {"name": name, "arguments": args if provider == "ollama" else json.dumps(args, ensure_ascii=False)}}
                for cid, name, args in calls]})
            for cid, name, args in calls:
                sig = (name, json.dumps(args, sort_keys=True, ensure_ascii=False))
                if sig in seen:
                    obs = {"info": "appel déjà effectué avec les mêmes arguments : utilise les résultats précédents"}
                else:
                    seen.add(sig)
                    obs = self._run_tool(name, args, message, ctx, steps)
                content = json.dumps(obs, ensure_ascii=False, default=str)[:8000]
                messages.append({"role": "tool", "tool_name": name, "content": content} if provider == "ollama"
                                else {"role": "tool", "tool_call_id": cid, "content": content})
        return ""

    def chat_agentic(self, message, history=None, profile=None, topic=None):
        """Agentic Modular RAG : le LLM planifie, appelle les modules (outils), observe, relance si besoin, puis répond."""
        global LAST_MODEL
        history = self.history if history is None else history
        urgent = bool(RED_FLAGS.search(strip_accents(message.lower())))
        ctx, steps = {}, []
        if urgent:
            ctx["CONTEXTE_MEDICAL"] = {"urgent": True, "specialistes_recommandes": ["médecin généraliste"]}

        # la thématique choisie par le client déclenche d'office les modules correspondants (résultats fournis à l'agent)
        topic_first = topic if not history else None  # thématique imposée seulement au 1er tour
        for m in [m for m in topic_modules(topic_first) if m in self.valid_modules]:
            if m == "product":
                self._run_tool("search_products", {"query": message}, message, ctx, steps, source="thematique")
            elif m == "symptom":
                self._run_tool("advise_specialists", {"symptom_query": message}, message, ctx, steps, source="thematique")
            else:
                self._run_tool("search_services", {"query": message, "modules": [m]}, message, ctx, steps, source="thematique")

        hist = fmt_history(history)
        client_ctx = ""
        if profile or topic_first:
            client_ctx = "CONTEXTE_CLIENT:\n" + json.dumps(
                {"profil": profile, "consigne_ton": PROFILE_STYLES.get(profile or "", ""), "thematique": topic_first},
                ensure_ascii=False) + "\n\n"
        pre = ""
        if ctx:
            pre = "RÉSULTATS DÉJÀ OBTENUS :\n" + json.dumps(ctx, ensure_ascii=False, indent=1, default=str) + "\n\n"
        if urgent:
            pre += "ALERTE : signes de gravité détectés dans le message (CONTEXTE_MEDICAL.urgent = true).\n\n"
        prompt = (f"HISTORIQUE (contexte seulement, ne réponds plus aux anciens messages) :\n{hist or '(vide)'}\n\n"
                  f"MESSAGE UTILISATEUR À TRAITER MAINTENANT (réponds uniquement à celui-ci) :\n{message}\n\n{client_ctx}{pre}")

        errors = []
        answer, final_ctx, final_steps = "", ctx, steps
        for entry in LLM_CHAIN:
            provider, model = entry.split(":", 1)
            if provider not in ("groq", "ollama"):
                continue  # appels d'outils : Groq ou Ollama
            if provider == "groq" and not os.getenv("GROQ_API_KEY"):
                errors.append(f"{entry} : clé GROQ_API_KEY manquante")
                continue
            if _dead.get(entry, 0) > time.time():
                errors.append(f"{entry} : en pause (quota ou erreur récente)")
                continue
            c2, s2 = copy.deepcopy(ctx), list(steps)
            try:
                out = self._agent_loop(provider, model, [{"role": "system", "content": AGENT_SYSTEM},
                                               {"role": "user", "content": prompt}], c2, s2, message)
            except QuotaExhausted as e:
                _dead[entry] = time.time() + QUOTA_PAUSE_S
                errors.append(f"{entry} : quota journalier épuisé")
                print(f"  [fallback] {entry} : quota JOURNALIER épuisé -> modèle suivant ({str(e)[:160]})", file=sys.stderr)
                continue
            except ModelUnavailable as e:
                _dead[entry] = float("inf")
                errors.append(f"{entry} : modèle indisponible")
                print(f"  [fallback] {entry} : modèle introuvable -> modèle suivant ({str(e)[:160]})", file=sys.stderr)
                continue
            except Exception as e:
                _dead[entry] = time.time() + SOFT_PAUSE_S
                errors.append(f"{entry} : {type(e).__name__}")
                print(f"  [fallback] {entry} : {type(e).__name__}: {str(e)[:160]} -> modèle suivant", file=sys.stderr)
                continue
            out = clean_answer(out)
            if not out:
                errors.append(f"{entry} : réponse vide")
                continue
            LAST_MODEL, answer, final_ctx, final_steps = entry, out, c2, s2
            break
        if not answer:
            raise RuntimeError("Mode agent indisponible : " + " | ".join(errors or ["aucun modèle Groq ou Ollama dans LLM_CHAIN"]))

        answer = re.sub(r"\s*(€|\beuros?\b|\bEUR\b)", " DT", answer, flags=re.IGNORECASE)  # sécurité : jamais d'euro
        modules = list(dict.fromkeys(m for st in final_steps for m in st["modules"]))
        urgent = urgent or bool((final_ctx.get("CONTEXTE_MEDICAL") or {}).get("urgent"))
        if self.debug:
            for st in final_steps:
                print(f"[agent] étape {st['step']} {st['tool']}({json.dumps(st['args'], ensure_ascii=False)}) -> {st['observation']}", file=sys.stderr)
        history += [("Utilisateur", message), ("Assistant", answer)]
        return {"answer": answer, "intent": self.intent_label(modules), "modules": modules,
                "urgent": urgent, "profile": profile, "topic": topic, "context": final_ctx,
                "model": LAST_MODEL, "mode": "agentic", "steps": final_steps}

    def chat(self, message, history=None, profile=None, topic=None, rag=True):
        """Point d'entrée : Agentic Modular RAG ; repli automatique sur l'ancien pipeline si le mode agent échoue."""
        if AGENTIC and rag:
            try:
                return self.chat_agentic(message, history, profile, topic)
            except Exception as e:
                print(f"  [agent] mode agent indisponible ({type(e).__name__}: {str(e)[:200]}) -> pipeline RAG classique",
                      file=sys.stderr)
        return self.chat_pipeline(message, history, profile, topic, rag)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    agent = PharmaAgent(debug=args.debug)
    print("\nAssistant parapharmacie prêt. Décris ton besoin, tes symptômes ou ta question ('q' pour quitter).\n")
    while True:
        try:
            msg = input("Toi > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if msg.lower() in {"q", "quit", "exit"}:
            break
        if msg:
            print(f"\nAssistant > {agent.ask(msg)}\n")


if __name__ == "__main__":
    main()