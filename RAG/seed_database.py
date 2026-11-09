"""
seed_database.py
================
Génère ~50 conversations réalistes dans PostgreSQL pour alimenter le dashboard BI.
Couvre : 8 profils, 13 thèmes, 30 jours, scores variés.

Usage :
    cd C:/Users/samar/Desktop/PI/RAG
    python seed_database.py
"""
import json
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

import psycopg2
from psycopg2.extras import execute_values

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:nour@localhost:5432/callverse")

# ── Données de référence ──────────────────────────────────────────────────────
PROFILES = ["calme", "nerveux", "impatient", "mecontent", "fidele", "exigeant", "confus", "heureux"]
TOPICS   = ["facturation", "remboursement", "securite", "fidelite", "technique",
             "resiliation", "produit", "soins", "bebe_maman", "bien_etre",
             "precautions", "choix", "symptome"]
URGENCES = ["basse", "moyenne", "haute"]
VILLES   = ["Tunis", "Sfax", "Sousse", "Bizerte", "Nabeul", "Monastir", "Djerba", "Kairouan"]
PRENOMS  = ["Sana", "Amine", "Nour", "Yassine", "Rim", "Samir", "Fatma", "Mehdi",
             "Leila", "Karim", "Hana", "Adem", "Salma", "Omar", "Donia", "Bilel"]
NOMS     = ["Ben Ali", "Trabelsi", "Mansouri", "Karray", "Gharbi", "Saidi",
             "Jebali", "Chaabane", "Belhaj", "Ferchichi"]

MODELS   = ["qwen2.5:7b", "groq:openai/gpt-oss-20b"]

# Scores par profil : les clients mécontents/nerveux ont tendance à avoir des scores plus bas
SCORE_RANGES = {
    "calme":     (72, 95), "nerveux":   (55, 80), "impatient":  (58, 82),
    "mecontent": (42, 68), "fidele":    (78, 98), "exigeant":   (60, 85),
    "confus":    (50, 75), "heureux":   (80, 97),
}

TOPIC_BIAS = {  # Certains sujets sont naturellement plus difficiles à résoudre
    "facturation": -5, "remboursement": -8, "securite": -3, "symptome": -10,
    "resiliation": -6, "produit": 5, "bien_etre": 8, "bebe_maman": 3,
}

ADVISOR_MESSAGES = {
    "facturation":   ["Je comprends votre inquiétude concernant cette facture. Voici le détail des frais appliqués sur votre commande.",
                      "Après vérification, ce montant correspond aux frais de livraison express sélectionnés lors de votre achat."],
    "remboursement": ["Votre demande de remboursement a bien été enregistrée. Le virement sera effectué sous 5 à 7 jours ouvrés.",
                      "Je vais créer immédiatement un bon de retour pour votre produit. Vous recevrez un email de confirmation."],
    "produit":       ["Pour votre type de peau mixte, je vous recommande le gel nettoyant Avène Cleanance, très apprécié en Tunisie.",
                      "Ce shampooing sans sulfate de la gamme Bioderma conviendra parfaitement à votre cuir chevelu sensible."],
    "soins":         ["Pour une peau très sèche, la crème Lipikar de La Roche-Posay est idéale. Appliquez matin et soir.",
                      "Je vous conseille le sérum vitamine C d'Eucerin pour unifier votre teint et hydrater en profondeur."],
    "bebe_maman":    ["La crème Bébé Mustela est spécialement conçue pour les peaux sensibles des nourrissons, sans parfum ni parabène.",
                      "Pour les rougeurs de couche, le liniment oléo-calcaire reste la référence pédiatrique recommandée."],
    "technique":     ["Essayez de vider le cache de votre navigateur et de relancer la page. Si le problème persiste, contactez-nous.",
                      "Votre paiement a été refusé car votre plafond mensuel est atteint. Contactez votre banque pour l'augmenter."],
    "securite":      ["Ne cliquez surtout pas sur ce lien. C'est une tentative de phishing. Changez votre mot de passe immédiatement.",
                      "Votre compte a été sécurisé. Nous vous avons envoyé un email de confirmation de la modification."],
    "bien_etre":     ["La vitamine D3 associée au magnésium peut aider contre la fatigue chronique. Consultez votre médecin avant.",
                      "La mélatonine à faible dose (0.5mg) peut améliorer votre endormissement. Disponible en pharmacie sans ordonnance."],
    "choix":         ["En alternative, je vous propose le sérum Vichy Liftactiv, même efficacité avec un prix plus accessible.",
                      "Pour un budget limité, la gamme Garnier Skinactive offre un excellent rapport qualité-prix pour votre type de peau."],
    "precautions":   ["Les huiles essentielles sont contre-indiquées durant le premier trimestre. Consultez votre sage-femme.",
                      "Ce complément alimentaire peut interagir avec votre traitement. Demandez l'avis de votre médecin traitant."],
    "fidelite":      ["Votre abonnement Premium vous offre -15% sur toute la gamme et la livraison gratuite dès 30 TND.",
                      "Vos points de fidélité expirent dans 30 jours. Vous pouvez les utiliser sur votre prochaine commande."],
    "resiliation":   ["Votre résiliation a bien été prise en compte. Elle sera effective à la fin de votre période d'abonnement.",
                      "Avant de résilier, saviez-vous que nous proposons une pause de 3 mois pour les abonnés de longue date ?"],
    "symptome":      ["Pour ce type de symptôme, je vous recommande de consulter un dermatiologue. Voici les coordonnées des centres proches.",
                      "Ces douleurs persistantes nécessitent un avis médical. Je ne suis pas qualifié pour diagnostiquer, consultez un médecin."],
}

CLIENT_MESSAGES = [
    "Bonjour, j'ai un problème avec ma commande et j'ai besoin d'aide rapidement.",
    "Je voudrais comprendre pourquoi j'ai été débité deux fois ce mois-ci.",
    "Pouvez-vous m'aider à choisir le bon produit pour ma peau sensible ?",
    "Ma commande n'est pas encore arrivée, que se passe-t-il ?",
    "Je veux résilier mon abonnement, comment je fais ?",
    "J'ai reçu un SMS bizarre, est-ce que c'est de vous ?",
    "Quel produit conseillez-vous pour les cheveux secs et abîmés ?",
    "Je suis enceinte, puis-je utiliser ce soin corporel ?",
]


def rnd_score(profile: str, topic: str) -> int:
    lo, hi = SCORE_RANGES.get(profile, (60, 85))
    bias = TOPIC_BIAS.get(topic, 0)
    return max(20, min(100, random.randint(lo, hi) + bias))


def make_criteria(global_score: int) -> dict:
    def near(base):
        return max(0, min(100, base + random.randint(-12, 12)))
    return {
        "pertinence":   near(global_score),
        "exactitude":   near(global_score),
        "groundedness": near(global_score + 5),
        "empathie":     near(global_score - 3),
        "clarte":       near(global_score + 2),
        "conformite":   near(global_score - 5),
    }


def priority_from_score(score: int) -> str:
    if score >= 80: return "faible"
    if score >= 65: return "moyen"
    if score >= 50: return "eleve"
    return "critique"


def make_evaluation(conv_id: str, profile: str, topic: str, score: int) -> dict:
    criteria = make_criteria(score)
    prio = priority_from_score(score)
    requires_human = score < 55 or prio == "critique"
    alerts = []
    if score < 50:
        alerts.append("Score critique — intervention requise")
    if criteria["conformite"] < 50:
        alerts.append("Non-conformité réglementaire détectée")
    if criteria["empathie"] < 45:
        alerts.append("Manque d'empathie envers le client")
    return {
        "globalScore": score,
        "criteria": criteria,
        "strengths": random.sample(["Réponse claire", "Sources RAG utilisées", "Bonne empathie",
                                     "Résolution rapide", "Ton professionnel"], k=random.randint(1,3)),
        "improvements": random.sample(["Améliorer l'empathie", "Citer davantage de sources",
                                         "Réponse plus concise", "Vérifier la conformité"], k=random.randint(0,2)),
        "recommendations": [f"Adapter le ton au profil {profile}"],
        "alerts": alerts,
        "priority": prio,
        "requiresHumanReview": requires_human,
        "complianceCheck": "OK" if criteria["conformite"] >= 60 else "ATTENTION",
        "mode": "gemini-llm",
        "loraRisk": {"label": "OK", "status": "disabled"},
        "ragReference": {"used": True},
        "accuracyStatus": "verified" if score >= 70 else "uncertain",
        "profile": profile,
    }


def make_workforce(conv_id: str, score: int, profile: str) -> dict:
    prio = priority_from_score(score)
    status = "OPTIMAL" if score >= 72 else "INTERVENTION_REQUISE"
    actions = []
    problems = []
    if score < 72:
        problems.append(f"Score qualité insuffisant ({score}/100)")
    if score < 55:
        actions.append({"type": "escalade_humain", "description": "Transfert superviseur", "priority": 1, "responsible": "superviseur"})
    if score < 65:
        actions.append({"type": "relancer_rag", "description": "Réinterroger la base documentaire", "priority": 2, "responsible": "system"})
    if prio in ("eleve", "critique"):
        actions.append({"type": "formation", "description": f"Module sensibilisation profil {profile}", "priority": 3, "responsible": "RH"})
    if random.random() < 0.3:
        actions.append({"type": "signaler_kb", "description": "Mise à jour fiche produit recommandée", "priority": 4, "responsible": "KB"})
    has_esc = any(a["type"] == "escalade_humain" for a in actions)
    return {
        "agent": "workforce-manager",
        "auditScore": score,
        "status": status,
        "problems": problems,
        "actions": actions,
        "workforceSummary": {
            "staffingImpact": "Aucun impact" if status == "OPTIMAL" else "Surcharge superviseur possible",
            "trainingModuleSuggested": f"Gestion profil {profile}" if prio != "faible" else None,
            "kbUpdateRequired": any(a["type"] == "signaler_kb" for a in actions),
        },
        "decidedAt": datetime.now(timezone.utc).isoformat(),
    }


def seed():
    print("🌱 Démarrage du seed de données...\n")
    conn = psycopg2.connect(DATABASE_URL)
    print("✅ Connexion PostgreSQL OK\n")

    n_days = 30
    n_convs = 50
    base_date = datetime.now(timezone.utc) - timedelta(days=n_days)

    conversations_inserted = 0
    quality_inserted = 0
    workforce_inserted = 0

    try:
        with conn:
            cur = conn.cursor()

            for i in range(n_convs):
                profile = random.choice(PROFILES)
                topic   = random.choice(TOPICS)
                urgency = random.choice(URGENCES)
                prenom  = random.choice(PRENOMS)
                nom     = random.choice(NOMS)
                age     = random.randint(22, 65)
                ville   = random.choice(VILLES)
                client_name = f"{prenom} {nom}"
                n_turns = random.randint(1, 3)
                model   = random.choice(MODELS)

                # Date aléatoire sur les 30 derniers jours (plus de conversations récentes)
                weight = random.random() ** 0.5  # biais vers les jours récents
                dt = base_date + timedelta(days=weight * n_days,
                                            hours=random.randint(7, 22),
                                            minutes=random.randint(0, 59))
                conv_id = str(uuid.uuid4())
                score = rnd_score(profile, topic)
                latency = random.randint(800, 8000)

                # 1) Insert client
                cur.execute("""
                    INSERT INTO sim_clients (name, age, city, profile, created_at)
                    VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT (name, age, city, profile) DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                """, (client_name, age, ville, profile, dt))
                client_id = cur.fetchone()[0]

                # 2) Insert conversation
                cur.execute("""
                    INSERT INTO sim_conversations
                    (id, client_id, created_at, profile, topic, urgency, rag,
                     requested_messages, completed_turns, client_name, client_age, client_city,
                     client_model, advisor_model, total_latency_ms, any_urgent)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO NOTHING
                """, (conv_id, client_id, dt, profile, topic, urgency, True,
                      n_turns, n_turns, client_name, age, ville,
                      "qwen-client-v2", model, latency, urgency == "haute"))
                conversations_inserted += 1

                # 3) Insert turns
                adv_msgs = ADVISOR_MESSAGES.get(topic, ["Je vais vous aider à résoudre ce problème."])
                turns_rows = []
                for t in range(1, n_turns + 1):
                    client_msg = random.choice(CLIENT_MESSAGES)
                    adv_msg = random.choice(adv_msgs)
                    turns_rows.append((conv_id, t, "client", client_msg, len(client_msg.split()), 0, "qwen-client-v2", topic, False, None, None, 0, 0))
                    turns_rows.append((conv_id, t, "advisor", adv_msg, len(adv_msg.split()), random.randint(300, 3000), model, topic, urgency=="haute", "soins,parapharmacie", None, random.randint(2,8), random.randint(1,4)))
                execute_values(cur, """
                    INSERT INTO sim_turns
                    (conversation_id, turn, role, content, word_count, latency_ms, model,
                     intent, urgent, modules, specialists, n_sources, n_steps)
                    VALUES %s ON CONFLICT (conversation_id, turn, role) DO NOTHING
                """, turns_rows)

                # 4) Insert sources RAG
                n_sources = random.randint(2, 6)
                source_rows = [(conv_id, 1, f"src_{j}", f"Fiche {topic} #{j+1}", random.choice(["soins","parapharmacie","ecommerce"]), round(random.uniform(0.6, 0.99), 3)) for j in range(n_sources)]
                execute_values(cur, "INSERT INTO sim_sources (conversation_id, turn, source_id, title, module, score) VALUES %s", source_rows)

                # 5) Insert quality evaluation
                evaluation = make_evaluation(conv_id, profile, topic, score)
                criteria = evaluation["criteria"]
                lora = evaluation.get("loraRisk", {})
                rag_ref = evaluation.get("ragReference", {})
                cur.execute("""
                    INSERT INTO quality_evaluations
                    (conversation_id, global_score,
                     score_pertinence, score_exactitude, score_groundedness,
                     score_empathie, score_clarte, score_conformite,
                     priority, requires_human_review, compliance_check,
                     strengths, improvements, recommendations, alerts,
                     mode, lora_risk_label, lora_risk_status,
                     rag_reference_used, accuracy_status, profile, raw_json)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    conv_id, score,
                    criteria["pertinence"], criteria["exactitude"], criteria["groundedness"],
                    criteria["empathie"], criteria["clarte"], criteria["conformite"],
                    evaluation["priority"], evaluation["requiresHumanReview"], evaluation["complianceCheck"],
                    " | ".join(evaluation["strengths"]),
                    " | ".join(evaluation["improvements"]),
                    " | ".join(evaluation["recommendations"]),
                    " | ".join(evaluation["alerts"]),
                    "gemini-llm", lora.get("label"), lora.get("status"),
                    rag_ref.get("used", True), evaluation["accuracyStatus"],
                    profile, json.dumps(evaluation, ensure_ascii=False)
                ))
                quality_inserted += 1

                # 6) Insert workforce decision
                decision = make_workforce(conv_id, score, profile)
                actions = decision.get("actions", [])
                wf = decision.get("workforceSummary", {})
                action_types = ", ".join({a.get("type","") for a in actions})
                cur.execute("""
                    INSERT INTO workforce_decisions
                    (conversation_id, audit_score, status, problems, nb_actions, action_types,
                     has_escalation, has_rag_relaunch, has_kb_signal, has_training,
                     staffing_impact, training_module, kb_update_required, raw_json)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    conv_id, score, decision["status"],
                    " | ".join(decision["problems"]),
                    len(actions), action_types,
                    any(a["type"]=="escalade_humain" for a in actions),
                    any(a["type"]=="relancer_rag" for a in actions),
                    any(a["type"]=="signaler_kb" for a in actions),
                    any(a["type"]=="formation" for a in actions),
                    wf.get("staffingImpact"), wf.get("trainingModuleSuggested"),
                    bool(wf.get("kbUpdateRequired")),
                    json.dumps(decision, ensure_ascii=False)
                ))
                workforce_inserted += 1

                print(f"  [{i+1:02d}/50] ✅ {profile:10s} | {topic:15s} | score={score:3d} | {decision['status']}")

    finally:
        conn.close()

    print(f"\n{'='*55}")
    print(f"✅ Seed terminé !")
    print(f"   Conversations : {conversations_inserted}")
    print(f"   Évaluations   : {quality_inserted}")
    print(f"   Workforce      : {workforce_inserted}")
    print(f"{'='*55}")
    print("\n🚀 Recharge le dashboard — tu devrais voir toutes les données !")


if __name__ == "__main__":
    seed()
