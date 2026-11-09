#!/usr/bin/env python3
"""
PIADSP - Agent MODULAR RAG E-commerce + Parapharmacie (MaPara Tunisie) avec Gemini.

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
import time
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()  # "gemini" ou "groq"
GEN_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
EMBED_BACKEND = os.getenv("EMBED_BACKEND", "local").lower()  # "local" (défaut) ou "gemini"
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
LOCAL_EMBED_MODEL = os.getenv("LOCAL_EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
EMBED_DIM = 768
ROUTER_LORA_PATH = os.getenv("ROUTER_LORA_PATH", "")  # dossier de l'adaptateur LoRA du routeur (vide = routeur LLM seul)
EMBED_BATCH = int(os.getenv("EMBED_BATCH", "100"))
EMBED_SLEEP = float(os.getenv("EMBED_SLEEP", "2"))  # pause entre lots (quota gratuit)

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
MODULES_DIR = Path(os.getenv("MODULES_DIR", str(DATA_DIR / "modules")))
CACHE_DIR = Path(os.getenv("CACHE_DIR", ".cache"))
TODAY = os.getenv("TODAY") or date.today().isoformat()  # AAAA-MM-JJ ; sert à détecter les offres expirées

K_IN_STOCK = 5          # candidats en stock envoyés au LLM
K_OUT_OF_STOCK = 3      # candidats en rupture envoyés au LLM
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.50" if EMBED_BACKEND == "gemini" else "0.35"))
MARGIN = float(os.getenv("MARGIN", "0.04"))
LEX_W = float(os.getenv("LEX_W", "0.30"))  # poids du recoupement de mots (nom + catégories) ajouté au score d'embedding
_LEX_STOP = {"pour", "avec", "dans", "sans", "anti", "plus", "tres", "trop", "quel", "quelle", "quels", "cherche",
             "veux", "voudrais", "besoin", "budget", "mais", "contre", "soin", "soins", "produit", "produits", "max",
             "maximum", "dinar", "dinars", "tnd"}


def lex_stems(text):
    """Racines (4 premières lettres) des mots utiles : 'hydratante'/'hydratant' -> 'hydr', 'crème' -> 'crem'."""
    toks = re.findall(r"[a-z0-9]+", strip_accents(str(text).lower()))
    return {t[:4] for t in toks if len(t) >= 4 and not t.isdigit() and t not in _LEX_STOP}  # écart pour dire "le + adapté est en rupture"
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


def with_retry(fn, tries=6):
    for attempt in range(tries):
        try:
            return fn()
        except Exception as e:  # quota 429, 503, réseau...
            if type(e).__name__ in {"NotFoundError", "AuthenticationError", "PermissionDeniedError", "BadRequestError"}:
                # erreur de configuration (modèle inexistant, clé invalide) : inutile de réessayer
                raise RuntimeError(f"Erreur de configuration Groq (vérifie GROQ_MODEL / GROQ_API_KEY dans .env) : {e}") from e
            msg = str(e)
            if "PerDay" in msg or "per day" in msg.lower():
                raise RuntimeError(
                    "Quota JOURNALIER épuisé (palier gratuit). Embeddings : mets EMBED_BACKEND=local. "
                    "Génération : change LLM_PROVIDER (gemini/groq), réessaie demain ou passe en palier payant. "
                    f"Détail API : {str(e)[:300]}") from e
            if attempt == tries - 1:
                raise
            wait = min(5 * 2 ** attempt, 60)
            print(f"  [retry {attempt + 1}/{tries - 1}] {type(e).__name__}: attente {wait}s", file=sys.stderr)
            time.sleep(wait)


def generate(prompt, system=None, json_mode=False, temperature=0.3):
    if LLM_PROVIDER == "groq":
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        kw = {"response_format": {"type": "json_object"}} if json_mode else {}
        # gpt-oss est un modèle "raisonneur" : sans limite, il dépense ses tokens à réfléchir et peut renvoyer une réponse VIDE
        # (et il consomme beaucoup de quota). "low" = moins de réflexion. Désactivable : GROQ_REASONING_EFFORT= (vide)
        effort = os.getenv("GROQ_REASONING_EFFORT", "low")
        if "gpt-oss" in GROQ_MODEL and effort:
            kw["extra_body"] = {"reasoning_effort": effort}
        text = ""
        for _ in range(2):  # une 2e tentative si la réponse est vide
            r = with_retry(lambda: groq_client().chat.completions.create(
                model=GROQ_MODEL, messages=msgs, temperature=temperature, **kw))
            text = (r.choices[0].message.content or "").strip()
            if text:
                break
        return text

    from google.genai import types

    cfg = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json" if json_mode else None,
    )
    r = with_retry(lambda: client().models.generate_content(model=GEN_MODEL, contents=prompt, config=cfg))
    return (r.text or "").strip()


# --------------------------------------------------------------------------- #
# Embeddings (Gemini ou local) + cache disque
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


def cached_embed(name, texts):
    """Embeddings de documents, mis en cache sur disque (reprise possible si coupure)."""
    CACHE_DIR.mkdir(exist_ok=True)
    backend = EMBED_BACKEND + ("-" + LOCAL_EMBED_MODEL if EMBED_BACKEND == "local" else "-" + GEMINI_EMBED_MODEL)
    key = hashlib.sha1((backend + "\n".join(texts)).encode()).hexdigest()[:12]
    final = CACHE_DIR / f"{name}_{key}.npy"
    partial = CACHE_DIR / f"{name}_{key}.partial.npy"
    if final.exists():
        return np.load(final)

    done = np.load(partial) if partial.exists() else np.zeros((0, 1), dtype=np.float32)
    start = len(done)
    chunk = EMBED_BATCH * 5
    parts = [done] if start else []
    print(f"Indexation '{name}' : {len(texts)} documents (reprise à {start})...", file=sys.stderr)
    for i in range(start, len(texts), chunk):
        parts.append(_embed_raw(texts[i:i + chunk], "doc"))
        np.save(partial, np.vstack(parts))
    mat = np.vstack(parts)
    np.save(final, mat)
    partial.unlink(missing_ok=True)
    return mat


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
        self.vec = cached_embed(f"mod_{name}", texts)

    @staticmethod
    def doc_text(d):
        kw = ", ".join(d.get("mots_cles", []))
        return f"{d.get('titre', '')}. {d.get('contenu', '')} Mots-clés : {kw}"

    def search(self, qv, k=K_SERVICE_PER_MODULE):
        """Top-k des documents de référence (politiques, FAQ, offres...) + au plus 2 exemples fictifs."""
        s = self.vec @ qv
        order = np.argsort(-s)
        main = [i for i in order if self.docs[i].get("type") not in EXAMPLE_TYPES][:k]
        ex = [i for i in order if self.docs[i].get("type") in EXAMPLE_TYPES][:2]
        return [(float(s[i]), self.docs[i]) for i in main + ex]


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
- "urgent" = true uniquement pour des signes de gravité (douleur thoracique, difficulté à respirer, perte de
  connaissance, paralysie, hémorragie, idées suicidaires, gonflement du visage/gorge...)."""


ANSWER_SYSTEM = """Tu es l'assistant conseil d'une parapharmacie en ligne tunisienne (MaPara Tunisie).
Réponds dans la langue de l'utilisateur (français par défaut), ton chaleureux, clair et concis.
Si le message contient plusieurs demandes, traite chacune dans l'ordre, brièvement.
Ne commence pas par « Bonjour » sauf si HISTORIQUE est vide.

RÈGLES GÉNÉRALES
- Utilise UNIQUEMENT les produits fournis dans CONTEXTE_PRODUITS. N'invente jamais de produit, de prix, de lien ni de composition.
- Ne pose pas de diagnostic et ne recommande aucun médicament ni dosage.
- Les prix sont en dinars tunisiens : écris-les EXACTEMENT comme fournis dans le champ "prix" (ex. « 68,10 DT »). N'utilise JAMAIS le symbole € ni le mot euro, ne convertis rien.

BRANCHE PRODUIT (scénario fourni dans CONTEXTE_PRODUITS.scenario)
PRIORITÉ ABSOLUE : les produits EN STOCK passent toujours en premier.
- "in_stock" : recommande 1 à 3 produits EN STOCK, du plus adapté au moins adapté. Pour chacun : nom, marque, prix (champ "prix"),
  pourquoi il convient au besoin exprimé, et le lien pour commander. Indique qu'il est disponible.
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
class PharmaAgent:
    def __init__(self, debug=False):
        self.debug = debug
        self.history = []  # [(role, text)]

        # --- module product
        self.catalog = load_catalog()
        docs = [product_doc(r) for r in self.catalog.to_dict("records")]
        self.pvec = cached_embed("products", docs)
        self.in_idx = np.where(self.catalog["in_stock"].values)[0]
        self.out_idx = np.where(~self.catalog["in_stock"].values)[0]

        # --- module symptom
        self.specialties = load_specialties()
        self.valid_specialties = set(self.specialties["specialty"])
        self.svec = cached_embed("specialties", self.specialties["doc"].tolist())
        self.diseases = load_diseases(self.valid_specialties)
        self.dvec = cached_embed("diseases", self.diseases["doc"].tolist())

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

        # --- routeur local fine-tuné (LoRA), optionnel : le routeur LLM reste le filet de sécurité
        self.local_router = None
        if ROUTER_LORA_PATH:
            try:
                from local_router import LocalRouter

                self.local_router = LocalRouter(ROUTER_LORA_PATH)
                print(f"Routeur LoRA chargé depuis {ROUTER_LORA_PATH}", file=sys.stderr)
            except Exception as e:
                print(f"  [attention] routeur LoRA indisponible ({type(e).__name__}: {e}) -> routeur LLM", file=sys.stderr)

        print(f"Catalogue : {len(self.in_idx)} en stock, {len(self.out_idx)} en rupture | "
              f"{len(self.diseases)} maladies indexées | modules service : "
              f"{', '.join(f'{n} ({len(m.docs)})' for n, m in self.services.items()) or 'aucun'}.", file=sys.stderr)

    # ---- routage ---------------------------------------------------------- #
    def route(self, message, history):
        hist = "\n".join(f"{r}: {t}" for r, t in history[-HISTORY_TURNS:])
        prompt = f"HISTORIQUE:\n{hist or '(vide)'}\n\nDERNIER MESSAGE:\n{message}"
        data, source = None, "llm"
        # LoRA local : seulement pour les messages autonomes (le modèle est entraîné sans historique).
        # Question de suivi courte avec historique, ou sortie invalide -> routeur LLM.
        if self.local_router is not None and (not history or len(message.split()) > 6):
            try:
                data = self.local_router.route(message)
            except Exception:
                data = None
            if data is not None:
                source = "lora"
        if data is None:
            try:
                data = json.loads(generate(prompt, system=self.router_system, json_mode=True, temperature=0))
            except json.JSONDecodeError:  # sortie invalide uniquement ; le quota (RuntimeError) remonte
                data = {"modules": ["product"], "product_query": message, "symptom_query": "", "service_query": "",
                        "urgent": False, "max_price_tnd": None}
        data["router"] = source
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
        s = self.pvec @ embed_query(query)
        # recoupement lexical : le sens (embedding) seul remonte des produits "proches" mais hors sujet
        if LEX_W > 0:
            if not hasattr(self, "_p_stems"):
                self._p_stems = [lex_stems(f"{n} {c}") for n, c in zip(self.catalog["name"], self.catalog["categories"])]
            q_st = lex_stems(query)
            if q_st:
                frac = np.array([len(q_st & st) / len(q_st) for st in self._p_stems])
                s = s + LEX_W * frac
        prices = self.catalog["price_tnd"].values

        def allowed(idx):
            if max_price is None:
                return idx
            return np.array([i for i in idx if pd.isna(prices[i]) or prices[i] <= max_price], dtype=int)

        in_idx, out_idx = allowed(self.in_idx), allowed(self.out_idx)
        top_in = in_idx[np.argsort(-s[in_idx])[:K_IN_STOCK]] if len(in_idx) else []
        top_out = out_idx[np.argsort(-s[out_idx])[:K_OUT_OF_STOCK]] if len(out_idx) else []

        in_list = [i for i in top_in if s[i] >= MIN_SCORE]
        out_list = [i for i in top_out if s[i] >= MIN_SCORE]

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
        sd = self.dvec @ qv
        top_d = np.argsort(-sd)[:TOP_DISEASES]
        scores = defaultdict(float)
        pistes = []
        for i in top_d:
            row = self.diseases.iloc[i]
            for sp in row["spec_list"]:
                scores[sp] += max(float(sd[i]), 0.0)
            pistes.append({"maladie": row["disease"], "symptomes": row["symptoms"],
                           "specialites": row["spec_list"]})

        # 2) spécialités proches (specialties.csv)
        ss = self.svec @ qv
        top_s = np.argsort(-ss)[:TOP_SPECIALTIES]
        proches = [{"specialite": self.specialties.iloc[i]["specialty"],
                    "symptomes_typiques": self.specialties.iloc[i]["top_symptoms"]} for i in top_s]
        for i in top_s:
            scores[self.specialties.iloc[i]["specialty"]] += max(float(ss[i]), 0.0)

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
            data = json.loads(generate(prompt, system=SPECIALTY_SELECTOR_SYSTEM, json_mode=True, temperature=0))
            chosen = [x for x in data.get("specialties", []) if x in self.valid_specialties][:3]
        except Exception:
            pass
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

    def chat(self, message, history=None):
        """history : liste [(role, texte)] propre à la session (par défaut l'historique du CLI)."""
        history = self.history if history is None else history
        route = self.route(message, history)
        modules = route["modules"]
        context = {}

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

        hist = "\n".join(f"{r}: {t}" for r, t in history[-HISTORY_TURNS:])
        payload = {k: v for k, v in context.items() if not k.startswith("_")}
        prompt = (
            f"HISTORIQUE:\n{hist or '(vide)'}\n\n"
            f"MESSAGE UTILISATEUR:\n{message}\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=1) if payload else '(aucun contexte : réponds brièvement et propose ton aide pour un conseil produit, des symptômes ou une question sur une commande, un paiement, une offre ou ton compte)'}"
        )
        # réponses de service : température basse pour coller aux documents (pas d'invention de procédure)
        answer = generate(prompt, system=ANSWER_SYSTEM, temperature=0.1 if "CONTEXTE_SERVICE" in payload else 0.3)
        answer = re.sub(r"\s*(€|\beuros?\b|\bEUR\b)", " DT", answer, flags=re.IGNORECASE)  # sécurité : jamais d'euro
        history += [("Utilisateur", message), ("Assistant", answer)]
        return {"answer": answer, "intent": route["intent"], "modules": modules,
                "urgent": route["urgent"], "context": payload}


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
            try:
                print(f"\nAssistant > {agent.ask(msg)}\n")
            except RuntimeError as e:  # quota épuisé : on n'arrête pas le programme
                print(f"\n[Erreur API] {e}\n")


if __name__ == "__main__":
    main()