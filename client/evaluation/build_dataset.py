"""Fine-tuning – étape 1 : construire le dataset d'entraînement.

Un modèle « professeur » (plus fort) génère des premiers messages avec le prompt
exact de l'app, puis des filtres automatiques ne gardent que les bons exemples.

Les sujets d'entraînement sont DIFFÉRENTS des sujets d'évaluation
(SUJETS_PAR_DEFAUT), pour ne pas fausser l'évaluation après fine-tuning.

Lancer depuis la racine du back (client_agent/) :
    python -m evaluation.build_dataset --prof qwen2.5:7b --par-profil 80
    python -m evaluation.build_dataset --prof qwen2.5:7b --par-profil 80 --juge-filtre llama3.1:8b
"""
import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path

from app.client_generator import generate_client
from app.llm_service import generate_response
from app.profiles import PROFILES, SUJETS_PAR_DEFAUT
from app.prompt_builder import URGENCY_HINT, build_client_prompt

# Sujets d'entraînement : aucun ne doit être dans SUJETS_PAR_DEFAUT (sujets d'évaluation)
SUJETS_TRAIN = [
    "prendre un rendez-vous chez un pédiatre pour son enfant",
    "obtenir un certificat médical pour le sport",
    "annuler un rendez-vous",
    "prendre un rendez-vous chez un ophtalmologue",
    "connaître les horaires d'ouverture du centre",
    "prendre un rendez-vous chez un gynécologue",
    "se faire vacciner contre la grippe",
    "prendre un rendez-vous chez un dentiste",
    "voir un kinésithérapeute après une entorse",
    "passer une radio du genou",
    "faire le suivi de son diabète",
    "prendre un rendez-vous chez un ORL",
    "prolonger un arrêt de travail",
    "connaître le tarif d'une consultation",
    "obtenir une facture pour le remboursement",
    "demander une téléconsultation",
    "faire une prise de sang à domicile",
    "prendre un rendez-vous chez un psychologue",
    "changer de médecin traitant",
    "obtenir le compte-rendu d'une consultation",
    "prendre un rendez-vous chez un nutritionniste",
    "passer une échographie",
    "faire les vaccins avant un voyage",
    "prendre un rendez-vous chez un cardiologue pour un contrôle",
    "transmettre son dossier médical à un autre médecin",
]
assert not set(SUJETS_TRAIN) & set(SUJETS_PAR_DEFAUT), "un sujet d'entraînement est aussi un sujet d'évaluation"

# Consigne supplémentaire donnée au professeur seulement (elle n'est PAS dans le dataset)
CONSIGNE_PROF = """
EXIGENCES STRICTES :
- Au maximum deux phrases et 35 mots.
- Tu es au téléphone, pas sur place.
- Aucun nom de médecin, aucune date ni heure précise inventée.
- Le ton du profil doit s'entendre dès la première phrase.
- Ne t'adresse pas à ton interlocuteur par un titre (« Monsieur le conseiller », « Madame »...).
- Commence ta phrase de façon naturelle et variée, comme une vraie personne.
- Ne recopie PAS les expressions données entre « » dans ton style : trouve tes propres mots.
- Parle à la première personne (« je »), ne raconte pas la scène.
"""
# Consigne en plus, propre à certains profils (professeur uniquement, PAS dans le dataset)
CONSIGNE_PAR_PROFIL = {
    "fidele": "- Dis clairement que tu es patient du centre depuis des années, avec chaleur et familiarité.\n",
    "exigeant": "- Formule UNE exigence précise, choisie librement (un délai strict, une garantie, un justificatif, "
                "un créneau précis, le meilleur spécialiste, une réponse immédiate...). Ne demande PAS systématiquement "
                "une confirmation écrite ni le nom du médecin.\n",}

RE_ANCIENNETE = re.compile(
    r"depuis (des années|longtemps|toujours|\d+ ans|tant d'années)|ça fait (des années|longtemps)|"
    r"patiente? (de la maison|régulier|régulière|fidèle|habituel|habituelle|de longue date)|"
    r"comme d'habitude|comme toujours|habitué|je viens chez vous|vous me connaissez|toujours (été )?(bien )?(soigné|reçu|suivi)"
)
RE_EXIGENCE = re.compile(
    r"garanti|confirm|par écrit|écrit|précis|exact|immédiat|j'exige|exige|impérati|sans faute|"
    r"aujourd'hui même|au plus tard|le meilleur|je veux|il me faut|je tiens à"
)
RE_SOI_MEME = re.compile(r"(^|[.!?]\s*)\w+,\s*tu (es|sais|apprécies|as)\b|^bonjour \w+, c'est")
PHRASES_CONSEILLER = [
    "comment puis-je", "je suis là pour vous aider", "je vais vérifier", "en tant qu",
    "assistant", "je peux vous aider", "que puis-je faire pour vous", "pouvez-vous me dire quel est",
]
# un titre suivi d'un NOM PROPRE (majuscule) : « Dr Tarek », « Mme Lakhdar ». « le docteur qui... » n'est pas rejeté.
RE_MEDECIN = re.compile(r"\b(?i:docteur|dr\.?|professeur|pr\.?|mme|mlle|madame|monsieur|m\.)\s+[A-ZÀ-Ý][a-zà-ÿ]+")


def formule_exigeant(message: str) -> bool:
    """La formule recopiée « confirmation écrite + nom exact du médecin »."""
    m = message.lower()
    return "confirmation" in m and "nom exact" in m


MAX_FORMULE_EXIGEANT = 6   # on en garde quelques-uns, pas 30
RE_SUR_PLACE = re.compile(r"\b(je suis (ici|là) depuis|j'attends ici|depuis que je suis (ici|là))", re.IGNORECASE)
RE_HEURE = re.compile(r"\b\d{1,2}\s?(h|heures?)\s?\d{0,2}\b", re.IGNORECASE)


def nettoyer(texte: str) -> str:
    t = texte.strip().strip('"«» \n')
    for prefixe in ("Client :", "Client:", "Client –", "Client -"):
        if t.startswith(prefixe):
            t = t[len(prefixe):].strip()
    return t.strip('"«» \n')


def nb_phrases(texte: str) -> int:
    """Compte les phrases. Les points de suspension (« euh... ») ne terminent PAS une phrase,
    et une suite de petites questions (« c'est grave ? vous êtes sûr ? ») compte pour une seule."""
    t = re.sub(r"\.{2,}|…", " ", texte)          # enlève les points de suspension
    t = re.sub(r"\?(\s*[^.!?]{1,25}\?)+", "?", t)  # regroupe les petites questions qui se suivent
    return len([p for p in re.split(r"[.!?]+", t) if p.strip()])


def raison_rejet(message: str, profil: str) -> str | None:
    """Renvoie la raison du rejet, ou None si le message est bon."""
    m = message.lower()
    if not message or len(message.split()) < 4:
        return "trop_court"
    if len(message.split()) > 40 or nb_phrases(message) > 4:
        return "trop_long"
    if any(p in m for p in PHRASES_CONSEILLER):
        return "role_conseiller"
    if RE_MEDECIN.search(message):
        return "medecin_invente"
    if RE_HEURE.search(message):
        return "heure_inventee"
    if RE_SUR_PLACE.search(message):
        return "pas_au_telephone"
    if profil == "mecontent" and "merci" in m:
        return "mecontent_remercie"
    if "\n" in message or "(" in message:
        return "format"
    # recopie mot pour mot les exemples du « ton » dans profiles.py
    if re.search(r"et si\s*(\.\.\.|…)\s*\?", m) or ("c'est grave" in m and "vous êtes sûr" in m and "et si" in m):
        return "copie_consigne"
    if "pas le temps" in m and "perdre du temps" in m:
        return "copie_consigne"
    # raconte au lieu de parler (« Ines rappelle le centre... elle souhaite... »)
    if re.search(r"\b(elle|il) (souhaite|veut|appelle|rappelle|demande)\b", m):
        return "troisieme_personne"
    if re.match(r"(monsieur|madame)\b", m):
        return "titre"
    if RE_SOI_MEME.search(m):
        return "parle_a_soi_meme"
    # règles propres à certains profils
    if profil == "fidele" and "impatient" in m:
        return "fidele_impatient"
    if profil == "fidele" and not RE_ANCIENNETE.search(m):
        return "fidele_sans_anciennete"
    if profil == "exigeant" and not RE_EXIGENCE.search(m):
        return "exigeant_sans_exigence"
    return None


def debut(message: str) -> str:
    """Les 2 premiers mots du message (pour repérer les débuts répétitifs)."""
    mots = re.sub(r"[^\w\s']", " ", message.lower()).split()
    return " ".join(mots[:2])


def cle_doublon(message: str) -> str:
    mots = re.sub(r"[^\w\s]", "", message.lower()).split()
    return " ".join(mots[:8])


def profil_reconnu(message: str, profil: str, juge: str) -> bool:
    from evaluation.eval_profil import PROFILS, parser_reponse, prompt_juge
    ordre = PROFILS[:]
    random.shuffle(ordre)
    brut = generate_response(prompt_juge(message, ordre), model=juge, temperature=0.0)
    return parser_reponse(brut)[0] == profil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prof", default="qwen2.5:7b", help="modèle professeur qui écrit les exemples")
    parser.add_argument("--par-profil", type=int, default=80, help="exemples gardés par profil")
    parser.add_argument("--juge-filtre", default=None, help="si donné : garde seulement si ce juge reconnaît le profil")
    parser.add_argument("--out", default="eval/dataset/train.jsonl")
    parser.add_argument("--seed", type=int, default=123)
    args = parser.parse_args()

    random.seed(args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Reprise : on recompte ce qui existe déjà
    compte, vus, debuts = Counter(), set(), Counter()
    nb_formule = 0
    if out.exists():
        for ligne in out.read_text(encoding="utf-8").splitlines():
            if ligne.strip():
                ex = json.loads(ligne)
                compte[ex["profil"]] += 1
                vus.add(cle_doublon(ex["messages"][-1]["content"]))
                debuts[(ex["profil"], debut(ex["messages"][-1]["content"]))] += 1
                if ex["profil"] == "exigeant" and formule_exigeant(ex["messages"][-1]["content"]):
                    nb_formule += 1
    print(f"Déjà dans le dataset : {dict(compte) or 0}")

    # un même début de 2 mots ne peut pas dépasser 15 % des exemples d'un profil
    max_meme_debut = max(3, int(args.par_profil * 0.25))

    rejets = Counter()
    essais = 0
    with out.open("a", encoding="utf-8") as f:
        for profil in PROFILES:
            essais_profil = 0
            while compte[profil] < args.par_profil:
                essais += 1
                essais_profil += 1
                if essais_profil > args.par_profil * 8:   # limite PAR profil
                    print(f"Trop d'essais pour {profil} : on passe au profil suivant.")
                    break

                client = generate_client(essais)
                client.profil = profil
                topic = random.choice(SUJETS_TRAIN)
                urgence = random.choice(list(URGENCY_HINT))
                prompt_app = build_client_prompt(client, topic, urgence)   # prompt EXACT de l'app

                try:
                         brut = generate_response(
                        prompt_app + CONSIGNE_PROF + CONSIGNE_PAR_PROFIL.get(profil, ""),
                        model=args.prof,
                        max_tokens=100,
                    )
                except Exception as e:
                    print(f"   ! erreur LLM : {e}")
                    continue
                message = nettoyer(brut)

                raison = raison_rejet(message, profil)
                if raison is None and profil == "exigeant" and formule_exigeant(message) and nb_formule >= MAX_FORMULE_EXIGEANT:
                    raison = "formule_repetee"
                if raison is None and cle_doublon(message) in vus:
                    raison = "doublon"
                if raison is None and debuts[(profil, debut(message))] >= max_meme_debut:
                    raison = "debut_repetitif"
                if raison is None and args.juge_filtre and not profil_reconnu(message, profil, args.juge_filtre):
                    raison = "profil_non_reconnu"
                if raison:
                    rejets[raison] += 1
                    continue

                vus.add(cle_doublon(message))
                debuts[(profil, debut(message))] += 1
                if profil == "exigeant" and formule_exigeant(message):
                    nb_formule += 1
                compte[profil] += 1
                f.write(json.dumps({
                    "messages": [
                        {"role": "user", "content": prompt_app},
                        {"role": "assistant", "content": message},
                    ],
                    "profil": profil,
                    "topic": topic,
                    "urgency": urgence,
                }, ensure_ascii=False) + "\n")
                f.flush()
                print(f"[{profil:<10} {compte[profil]:>3}/{args.par_profil}] {message[:80]}")

    total = sum(compte.values())
    print("\n" + "=" * 60)
    print(f"Dataset : {total} exemples -> {out}")
    print(f"Par profil : {dict(compte)}")
    print(f"Essais : {essais}  |  taux d'acceptation : {total / max(essais, 1):.0%}")
    print(f"Raisons de rejet : {dict(rejets.most_common())}")


if __name__ == "__main__":
    main()