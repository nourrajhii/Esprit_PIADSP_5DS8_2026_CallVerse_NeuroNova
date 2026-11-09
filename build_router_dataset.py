#!/usr/bin/env python3
"""
Construit le jeu de données SFT du routeur (message -> JSON de routage) à partir de gabarits + de tes CSV.

Sorties : data/finetune/router_train.jsonl, router_val.jsonl  (format {"messages": [system, user, assistant]})
Le fichier 07_questions_test_routage.jsonl n'est JAMAIS utilisé pour l'entraînement : il sert uniquement de test.

Usage : python build_router_dataset.py [--n 2400] [--seed 42]
"""
import argparse
import json
import random
import re
import unicodedata
from pathlib import Path

from router_common import build_messages, make_target

DATA_DIR = Path("data")
OUT_DIR = DATA_DIR / "finetune"
TEST_FILE_CANDIDATES = [DATA_DIR / "modules" / "07_questions_test_routage.jsonl", DATA_DIR / "07_questions_test_routage.jsonl"]

# --------------------------------------------------------------------------- #
# Modules de service : (paraphrases, service_query)  — modules multiples possibles
# --------------------------------------------------------------------------- #
SERVICE_SEEDS = {
    "facturation_frais": [
        (["quel est le prix de la livraison à domicile", "la livraison coûte combien", "c'est quoi les frais de port",
          "à partir de quel montant la livraison est gratuite", "frais d'envoi pour ma commande"],
         "frais de livraison standard montant gratuit"),
        (["livraison rapide en 24h c'est combien", "tarif de la livraison express", "je veux être livré vite, quel tarif"],
         "frais de livraison express 24h"),
        (["comment récupérer ma facture", "je cherche ma facture de commande", "télécharger facture pdf",
          "j'ai besoin d'une facture pour ma commande"],
         "télécharger facture commande"),
        (["j'ai été prélevé deux fois pour la même commande", "double paiement sur ma carte", "mon compte a été débité 2 fois",
          "on m'a facturé en double"],
         "double débit paiement deux fois"),
        (["je veux une facture avec mon matricule fiscal", "facture pour mon entreprise avec MF", "facture professionnelle avec numéro fiscal"],
         "facture matricule fiscal"),
        (["comment changer mon adresse de facturation", "modifier l'adresse sur la facture", "mauvaise adresse de facturation"],
         "modifier adresse de facturation"),
        (["c'est quoi la ligne frais de service sur ma facture", "pourquoi des frais de service", "que signifie frais de paiement"],
         "ligne frais de service facture"),
        (["je peux payer à la livraison", "paiement en espèces à la réception", "est-ce qu'il y a des frais pour le paiement à la livraison"],
         "paiement à la livraison frais"),
        (["peut-on payer en 3 fois", "paiement échelonné possible", "payer en plusieurs fois sans frais"],
         "paiement en 3 fois"),
        (["la TVA est incluse dans les prix", "les prix sont TTC ou HT", "c'est quoi la tva sur mon achat"],
         "TVA prix TTC"),
        (["ma commande n'est pas confirmée mais j'ai payé", "paiement en attente, dois-je repayer", "payé mais pas de confirmation de commande"],
         "paiement en attente commande non confirmée"),
        (["ma commande a été annulée toute seule", "commande annulée automatiquement car non payée"],
         "annulation automatique commande non payée"),
    ],
    "remboursement_avoir": [
        (["je peux retourner un produit combien de temps après réception", "délai pour renvoyer un article", "quel est le délai de rétractation"],
         "délai de rétractation retour produit 14 jours"),
        (["je peux rendre un sérum que j'ai déjà ouvert", "retour d'un produit descellé possible", "mon produit de soin est ouvert, remboursable ?"],
         "retour produit ouvert hygiène non remboursable"),
        (["j'ai reçu un produit cassé", "on m'a livré le mauvais produit", "article défectueux à la réception", "produit abîmé dans le colis"],
         "produit défectueux ou erroné retour"),
        (["en combien de jours je serai remboursé", "quand vais-je recevoir mon remboursement", "délai de remboursement après retour"],
         "délai de remboursement"),
        (["qu'est-ce qu'un avoir exactement", "explique-moi le crédit boutique", "à quoi sert un avoir"],
         "avoir crédit boutique définition"),
        (["comment utiliser mon avoir pour une nouvelle commande", "payer avec mon avoir", "appliquer un avoir au paiement"],
         "utiliser un avoir lors d'une commande"),
        (["où voir le solde de mon avoir", "mon avoir expire quand", "validité de mon avoir"],
         "solde et validité avoir"),
        (["qui paie les frais de retour", "le renvoi du colis est gratuit", "frais pour retourner un produit"],
         "frais de retour"),
        (["le produit que j'ai payé est en rupture, que se passe-t-il", "commande payée mais article indisponible", "rupture de stock après paiement remboursement"],
         "rupture après paiement remboursement"),
        (["je peux avoir un remboursement partiel", "un seul article de ma commande à rembourser"],
         "remboursement partiel"),
        (["avoir ou remboursement sur ma carte, quelle différence", "je préfère un avoir au remboursement bancaire", "bonus sur l'avoir"],
         "avoir bonus remboursement choix"),
    ],
    "securite_alerte_sms": [
        (["j'ai reçu un message bizarre avec un lien de votre part", "sms douteux qui demande mes infos", "faux sms au nom de MaPara",
          "comment reconnaître un sms frauduleux"],
         "sms suspect phishing lien"),
        (["activer la sécurité renforcée de mon compte", "comment mettre la vérification en deux étapes", "mettre l'authentification à 2 facteurs"],
         "activer authentification à deux facteurs"),
        (["je n'ai pas reçu le code de vérification par sms", "où est mon code otp", "code de validation sms pas reçu"],
         "code OTP sms non reçu"),
        (["à quoi sert le code à 6 chiffres envoyé par sms", "puis-je donner mon code otp au conseiller", "durée de validité du code otp"],
         "code OTP 6 chiffres validité"),
        (["j'ai reçu une alerte de connexion que je ne reconnais pas", "sms nouvel appareil connecté, ce n'est pas moi", "quelqu'un s'est connecté à mon compte"],
         "alerte sms connexion nouvel appareil"),
        (["mon compte est bloqué après plusieurs essais", "compte suspendu tentatives de connexion échouées", "compte verrouillé comment le débloquer"],
         "compte suspendu tentatives échouées"),
        (["alerte paiement suspect sur ma carte", "j'ai reçu un sms de paiement que je n'ai pas fait"],
         "alerte paiement suspect"),
        (["comment changer mon numéro pour les sms", "modifier mon numéro de téléphone du compte"],
         "modifier numéro de téléphone"),
        (["mes données de santé sont-elles protégées", "est-ce que vous partagez mes données personnelles"],
         "protection données de santé personnelles"),
    ],
    "offres_fiabilite": [
        (["quelles sont les promos du moment", "vous avez des offres ce mois-ci", "les packs disponibles en ce moment",
          "y a-t-il des réductions en cours"],
         "offres et packs du mois promotions"),
        (["c'est quoi le mois gratuit", "comment profiter du premier mois offert", "essai gratuit premium comment ça marche"],
         "premier mois gratuit Premium"),
        (["parrainage comment ça marche", "puis-je parrainer un ami et gagner quelque chose", "code parrain avantage"],
         "parrainage"),
        (["avez-vous une offre de bienvenue", "réduction pour ma première commande"],
         "offre bienvenue première commande"),
        (["comment fonctionnent les points fidélité", "combien de points je gagne par achat", "à quoi servent mes points"],
         "points fidélité"),
        (["vos produits sont-ils authentiques", "est-ce que ce sont de vrais produits d'origine", "risque de contrefaçon sur le site"],
         "authenticité des produits"),
        (["comment vérifier la date de péremption", "les produits ont-ils une date limite assez longue"],
         "dates de péremption"),
        (["les avis clients sont-ils vrais", "avis vérifiés ou pas"],
         "avis clients vérifiés"),
        (["y a-t-il une garantie satisfait ou remboursé", "garantie sur mes achats"],
         "garantie satisfaction"),
        (["la livraison est-elle offerte en ce moment", "livraison gratuite ce mois"],
         "livraison offerte ce mois"),
        (["vous avez un pack bébé", "pack solaire ou immunité disponible ?", "quels packs pour la rentrée"],
         "packs du mois bébé solaire immunité"),
        (["vos conseils remplacent-ils un médecin", "l'assistant donne-t-il des avis médicaux"],
         "conseil non médical"),
    ],
    "panne_acces_services": [
        (["impossible d'ajouter un article à mon panier", "le bouton ajouter au panier ne marche pas", "quand j'ajoute un produit rien ne se passe",
          "mon panier ne prend pas le produit"],
         "impossible ajouter produit panier"),
        (["le bouton commander est bloqué", "je clique sur commander et rien ne bouge", "checkout qui ne répond pas"],
         "bouton commander ne répond pas"),
        (["ma carte est refusée au paiement", "le paiement échoue à chaque fois", "erreur lors du paiement par carte"],
         "paiement refusé erreur"),
        (["le site affiche une page blanche", "erreur serveur sur le site", "page d'erreur 502 ou 500", "le site plante"],
         "page blanche erreur 500 site"),
        (["je n'arrive pas à me connecter à mon compte", "connexion impossible, mot de passe refusé", "login qui ne marche pas"],
         "connexion impossible compte"),
        (["mon code promo est refusé", "le code de réduction ne s'applique pas"],
         "code promo non accepté"),
        (["le suivi de mon colis ne bouge pas", "tracking de commande pas à jour"],
         "suivi de colis pas à jour"),
        (["le chatbot ne répond plus", "l'assistant est en panne"],
         "chatbot conseil indisponible"),
        (["l'application mobile se ferme toute seule", "l'appli plante au démarrage"],
         "application mobile plante"),
        (["les images des produits ne s'affichent pas", "photos produits manquantes"],
         "images produits ne s'affichent pas"),
        (["le produit disparaît de mon panier", "mon panier se vide tout seul"],
         "produit disparaît du panier"),
        (["je ne peux pas augmenter la quantité dans le panier", "quantité limitée à 5 unités ?"],
         "impossible augmenter quantité panier"),
        (["le site est très lent", "les pages mettent une éternité à charger"],
         "site lent chargement"),
        (["y a-t-il une panne en ce moment", "est-ce que le paiement est en maintenance", "état des services du site"],
         "statut des services panne en cours"),
        (["je n'ai pas reçu l'e-mail de confirmation de commande", "mail de confirmation introuvable"],
         "e-mail confirmation commande non reçu"),
    ],
    "resiliation_contrat": [
        (["comment arrêter mon abonnement premium", "je ne veux plus de mon abonnement", "annuler mon abonnement",
          "désactiver le renouvellement premium"],
         "résilier abonnement Premium"),
        (["puis-je annuler pendant le mois gratuit sans être prélevé", "résilier l'essai gratuit avant le 30e jour"],
         "résilier pendant le mois gratuit"),
        (["faut-il un préavis pour résilier", "délai de préavis résiliation"],
         "préavis résiliation"),
        (["comment supprimer définitivement mon compte", "je souhaite fermer mon compte", "effacer mon compte et mes données"],
         "supprimer mon compte"),
        (["que deviennent mes avoirs si je ferme mon compte", "est-ce que je perds mes points fidélité en résiliant"],
         "avoirs et points après résiliation"),
        (["j'ai une commande en cours, puis-je résilier", "résiliation avec commande non livrée"],
         "commande en cours lors de la résiliation"),
        (["je veux arrêter de recevoir vos sms et mails", "comment me désabonner de la newsletter"],
         "se désabonner SMS et e-mails"),
        (["garder mon compte mais stopper les prélèvements", "arrêter les paiements automatiques sans supprimer le compte"],
         "garder le compte arrêter les prélèvements"),
    ],
}

# --------------------------------------------------------------------------- #
# Produits : (type de produit, besoins possibles)
# --------------------------------------------------------------------------- #
PRODUCTS = {
    "gel nettoyant visage": ["peau mixte à grasse", "peau sèche", "peau sensible", "peau à imperfections", "peau grasse et acné"],
    "crème hydratante visage": ["peau sèche", "peau mixte", "peau sensible", "peau normale", "peau déshydratée"],
    "sérum visage": ["anti-taches", "anti-âge", "peau terne", "peau grasse"],
    "eau micellaire": ["peau sensible", "peau grasse", "peau mixte", "démaquillage waterproof"],
    "crème solaire": ["SPF 50+ visage", "peau sensible", "enfant", "peau grasse"],
    "shampoing": ["cheveux gras", "cheveux secs", "anti-pellicules", "cheveux colorés", "anti-chute"],
    "masque visage": ["peau grasse", "peau sèche", "éclat"],
    "dentifrice": ["dents sensibles", "gencives fragiles", "blanchissant"],
    "bain de bouche": ["gencives sensibles", "haleine fraîche"],
    "déodorant": ["peau sensible", "transpiration forte", "sans aluminium"],
    "crème pour le corps": ["peau très sèche", "peau sensible", "vergetures"],
    "lait de toilette bébé": ["peau sensible", "change de bébé", "bébé de 3 mois"],
    "complément alimentaire": ["vitamine C", "défenses immunitaires", "magnésium fatigue", "cheveux et ongles", "énergie et vitalité"],
    "huile végétale": ["cheveux secs", "peau sèche", "massage"],
    "stick lèvres": ["lèvres gercées", "lèvres sèches"],
    "soin contour des yeux": ["cernes", "poches", "anti-rides"],
    "crème pour les mains": ["mains très sèches", "mains gercées"],
    "gel douche": ["peau sensible", "peau sèche", "usage quotidien"],
}
PRODUCT_TEMPLATES = [
    "je cherche {p} pour {n}", "tu me conseilles quel {p} pour {n} ?", "je voudrais un {p} adapté à {n}",
    "j'ai besoin d'un {p} ({n})", "quel {p} choisir pour {n}", "recommande-moi un {p} pour {n}",
    "je veux un {p}, j'ai {n}", "un bon {p} pour {n} svp", "avez-vous un {p} pour {n} ?",
]
BUDGET_PHRASES = [("moins de {x} dinars", None), ("max {x} DT", None), ("pas plus de {x} TND", None), ("budget {x} DT maximum", None)]

# --------------------------------------------------------------------------- #
# Symptômes : (phrase patient, symptom_query)   — la liste de spécialités vient des CSV, pas d'ici
# --------------------------------------------------------------------------- #
SYMPTOMS = [
    ("j'ai mal aux dents", "douleur dentaire"), ("j'ai une rage de dents depuis hier", "douleur dentaire"),
    ("mes gencives saignent quand je me brosse les dents", "saignement des gencives"),
    ("j'ai mal à la gorge et du mal à avaler", "mal de gorge"), ("j'ai les oreilles qui bourdonnent", "acouphènes"),
    ("j'ai mal à l'oreille depuis deux jours", "douleur à l'oreille"),
    ("j'ai des maux de tête très fréquents", "céphalée"), ("j'ai des migraines avec des nausées", "migraine nausées"),
    ("j'ai mal au ventre depuis ce matin", "douleur abdominale"), ("j'ai des brûlures d'estomac après les repas", "brûlures d'estomac"),
    ("j'ai la diarrhée depuis 3 jours", "diarrhée"), ("je suis constipé depuis une semaine", "constipation"),
    ("j'ai mal au dos en bas", "lombalgie douleur du bas du dos"), ("j'ai mal aux genoux quand je marche", "douleur du genou"),
    ("j'ai des douleurs aux articulations le matin", "douleurs articulaires"),
    ("j'ai des plaques rouges qui grattent sur les bras", "plaques rouges démangeaisons peau"),
    ("j'ai la vue qui baisse", "baisse de la vision"), ("j'ai les yeux rouges qui piquent", "rougeur des yeux"),
    ("j'ai de la toux depuis 10 jours", "toux persistante"), ("je suis essoufflé quand je monte les escaliers", "essoufflement à l'effort"),
    ("j'ai souvent soif et j'urine beaucoup", "soif intense urines fréquentes"), ("j'ai des brûlures en urinant", "brûlures urinaires"),
    ("je suis très fatigué en permanence", "fatigue persistante"), ("je n'arrive pas à dormir depuis des semaines", "insomnie"),
    ("je me sens très anxieux et triste ces derniers temps", "anxiété tristesse"), ("j'ai des palpitations de temps en temps", "palpitations"),
    ("mon enfant a de la fièvre depuis 2 jours", "fièvre chez l'enfant"), ("j'ai des vertiges quand je me lève", "vertiges"),
    ("j'ai les jambes lourdes et gonflées", "jambes lourdes gonflées"), ("j'ai des règles très douloureuses", "dysménorrhée règles douloureuses"),
]
URGENT_SYMPTOMS = [
    ("j'ai une douleur dans la poitrine qui irradie dans le bras", "douleur thoracique"),
    ("j'ai du mal à respirer d'un coup", "difficulté respiratoire"),
    ("mon père a perdu connaissance", "perte de connaissance"),
    ("j'ai le visage qui tombe d'un côté et je n'arrive plus à parler", "paralysie faciale difficulté à parler"),
    ("je vomis du sang", "vomissement de sang"), ("mon visage et ma gorge gonflent après avoir mangé", "gonflement du visage et de la gorge"),
    ("j'ai des idées suicidaires", "idées suicidaires"), ("je saigne abondamment et ça ne s'arrête pas", "saignement abondant"),
]
SYMPTOM_TEMPLATES = ["{s}", "{s}, que faire ?", "bonjour, {s}", "{s}. qui dois-je consulter ?", "{s}, vers quel médecin aller ?"]

CHITCHAT = ["bonjour", "salut", "bonsoir", "merci beaucoup", "merci c'est gentil", "ok merci", "au revoir", "à bientôt", "salam", "ça va ?",
            "qui es-tu ?", "tu peux m'aider ?", "quel temps fait-il à Tunis ?", "raconte-moi une blague", "c'est quoi la capitale de la France ?",
            "bonne journée", "super, parfait", "d'accord"]

# --------------------------------------------------------------------------- #
# Augmentation légère (bruit réaliste : accents, majuscules, politesse, fautes)
# --------------------------------------------------------------------------- #
PREFIXES = ["", "", "", "bonjour, ", "salut, ", "svp ", "s'il vous plaît, ", "bonsoir, "]
SUFFIXES = ["", "", "", " merci", " svp", " ?", " !", " urgent"]


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def noisy(text, rng):
    t = rng.choice(PREFIXES) + text + rng.choice(SUFFIXES)
    r = rng.random()
    if r < 0.12:
        t = strip_accents(t)
    elif r < 0.2:
        t = t.lower()
    elif r < 0.26 and len(t) > 12:  # une lettre doublée / supprimée
        i = rng.randrange(1, len(t) - 1)
        t = t[:i] + (t[i] if rng.random() < 0.5 else "") + t[i + 1:] if rng.random() < 0.5 else t[:i] + t[i] + t[i:]
    return re.sub(r"\s+", " ", t).strip()


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", strip_accents(s.lower())).strip()


# --------------------------------------------------------------------------- #
# Génération
# --------------------------------------------------------------------------- #
def gen_service(rng):
    mod = rng.choice(list(SERVICE_SEEDS))
    phrases, query = rng.choice(SERVICE_SEEDS[mod])
    return noisy(rng.choice(phrases), rng), make_target([mod], service_query=query)


def gen_product(rng):
    p = rng.choice(list(PRODUCTS))
    n = rng.choice(PRODUCTS[p])
    msg = rng.choice(PRODUCT_TEMPLATES).format(p=p, n=n)
    price = None
    if rng.random() < 0.25:
        price = rng.choice([20, 30, 40, 50, 60, 80, 100])
        msg += " " + rng.choice(BUDGET_PHRASES)[0].format(x=price)
    return noisy(msg, rng), make_target(["product"], product_query=f"{p} {n}", max_price=price)


def gen_symptom(rng):
    if rng.random() < 0.2:
        s, q = rng.choice(URGENT_SYMPTOMS)
        return noisy(rng.choice(SYMPTOM_TEMPLATES).format(s=s), rng), make_target(["symptom"], symptom_query=q, urgent=True)
    s, q = rng.choice(SYMPTOMS)
    return noisy(rng.choice(SYMPTOM_TEMPLATES).format(s=s), rng), make_target(["symptom"], symptom_query=q)


def gen_chitchat(rng):
    return noisy(rng.choice(CHITCHAT), rng), make_target([])


def gen_pack_product(rng):
    """Règle du routeur : pack/offre + type de produit => product ET offres_fiabilite, requête = besoin seul."""
    p = rng.choice(list(PRODUCTS))
    n = rng.choice(PRODUCTS[p])
    word = rng.choice(["un pack", "une offre", "une promo", "un pack promo"])
    msg = f"{word} pour {n}" if rng.random() < 0.5 else f"vous avez {word} avec {p} pour {n} ?"
    return noisy(msg, rng), make_target(["product", "offres_fiabilite"], product_query=f"soin {n}", service_query="offres et packs du mois promotions")


def gen_double_service(rng):
    combos = [
        (["paiement refusé mais mon compte est débité", "ma carte est refusée et pourtant j'ai été débité", "erreur de paiement et prélèvement quand même"],
         ["panne_acces_services", "facturation_frais"], "paiement refusé débit"),
        (["je n'arrive pas à utiliser mon avoir au paiement", "l'avoir ne s'applique pas dans le panier"],
         ["remboursement_avoir", "panne_acces_services"], "avoir non appliqué panier"),
        (["je veux résilier mon premium et être remboursé du mois", "résilier mon abonnement et récupérer mon argent"],
         ["resiliation_contrat", "remboursement_avoir"], "résiliation Premium remboursement"),
        (["je veux résilier mon abonnement car j'ai été prélevé deux fois", "prélèvement en double sur mon abonnement, je résilie"],
         ["resiliation_contrat", "facturation_frais"], "résiliation abonnement double prélèvement"),
        (["le code otp n'arrive pas pour valider mon paiement", "pas de sms de validation au moment de payer"],
         ["securite_alerte_sms", "panne_acces_services"], "code OTP non reçu paiement"),
        (["le mois gratuit premium est-il débité automatiquement après", "après le mois offert on me prélève quand"],
         ["offres_fiabilite", "resiliation_contrat", "facturation_frais"], "mois gratuit prélèvement après essai"),
    ]
    phrases, mods, q = rng.choice(combos)
    return noisy(rng.choice(phrases), rng), make_target(mods, service_query=q)


def gen_product_symptom(rng):
    s, sq = rng.choice(SYMPTOMS[:12])
    p = rng.choice(["dentifrice", "bain de bouche", "crème hydratante visage", "gel douche"])
    n = rng.choice(PRODUCTS[p])
    msg = f"{s} et je cherche aussi un {p} pour {n}"
    return noisy(msg, rng), make_target(["symptom", "product"], product_query=f"{p} {n}", symptom_query=sq)


GENERATORS = [
    (gen_service, 0.38), (gen_product, 0.22), (gen_symptom, 0.14), (gen_chitchat, 0.05),
    (gen_pack_product, 0.07), (gen_double_service, 0.09), (gen_product_symptom, 0.05),
]


def load_test_questions():
    for p in TEST_FILE_CANDIDATES:
        if p.exists():
            return {norm(json.loads(l)["question"]) for l in open(p, encoding="utf-8") if l.strip()}
    print("  [info] 07_questions_test_routage.jsonl introuvable : pas de filtre anti-fuite.")
    return set()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2400)
    ap.add_argument("--val_ratio", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    test_q = load_test_questions()
    funcs, weights = zip(*GENERATORS)
    seen, rows = set(), []
    attempts = 0
    while len(rows) < args.n and attempts < args.n * 20:
        attempts += 1
        msg, target = rng.choices(funcs, weights)[0](rng)
        k = norm(msg)
        if not k or k in seen or k in test_q:  # pas de doublon, pas de fuite vers le jeu de test
            continue
        seen.add(k)
        rows.append({"messages": build_messages(msg, target)})

    rng.shuffle(rows)
    n_val = max(1, int(len(rows) * args.val_ratio))
    val, train = rows[:n_val], rows[n_val:]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, data in (("router_train.jsonl", train), ("router_val.jsonl", val)):
        with open(OUT_DIR / name, "w", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"train={len(train)}  val={len(val)}  -> {OUT_DIR}")
    print("Exemple :", json.dumps(train[0]["messages"][1:], ensure_ascii=False))


if __name__ == "__main__":
    main()
