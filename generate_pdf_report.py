"""
Script de génération du rapport PDF - Base de données et Dashboard BI
Projet: Digital Twin Centre d'Assistance Client PharmaShop
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, 
                                 TableStyle, PageBreak, Image, KeepTogether)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from datetime import datetime
import os

# Configuration
OUTPUT_PATH = r"c:\Users\samar\Desktop\PI\Rapport_Database_Dashboard_BI.pdf"

# Couleurs du thème
PRIMARY_COLOR = HexColor('#8b5cf6')  # Violet
SECONDARY_COLOR = HexColor('#3b82f6')  # Bleu
SUCCESS_COLOR = HexColor('#22c55e')  # Vert
DANGER_COLOR = HexColor('#ef4444')  # Rouge
DARK_BG = HexColor('#1e1e2e')
LIGHT_TEXT = HexColor('#cdd6f4')

def add_header(canvas, doc):
    """En-tête personnalisé pour chaque page"""
    canvas.saveState()
    canvas.setFillColor(PRIMARY_COLOR)
    canvas.rect(0, A4[1] - 2*cm, A4[0], 2*cm, fill=True, stroke=False)
    canvas.setFillColor(white)
    canvas.setFont('Helvetica-Bold', 14)
    canvas.drawString(2*cm, A4[1] - 1.3*cm, "Digital Twin — Centre d'Assistance Client PharmaShop")
    canvas.setFont('Helvetica', 9)
    canvas.drawString(2*cm, A4[1] - 1.6*cm, "Base de données PostgreSQL & Dashboard BI")
    canvas.restoreState()

def add_footer(canvas, doc):
    """Pied de page avec numéro"""
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(HexColor('#666666'))
    page_num = canvas.getPageNumber()
    text = f"Page {page_num} — Rapport généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
    canvas.drawCentredString(A4[0] / 2, 1.5*cm, text)
    canvas.restoreState()

def create_pdf():
    """Génération du document PDF"""
    doc = SimpleDocTemplate(OUTPUT_PATH, pagesize=A4,
                            topMargin=2.5*cm, bottomMargin=2.5*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Style titre principal
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=PRIMARY_COLOR,
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Style titre de section
    section_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=SECONDARY_COLOR,
        spaceBefore=20,
        spaceAfter=12,
        fontName='Helvetica-Bold',
        borderWidth=0,
        borderColor=SECONDARY_COLOR,
        borderPadding=5,
        leftIndent=0
    )
    
    # Style sous-titre
    subsection_style = ParagraphStyle(
        'SubsectionTitle',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=PRIMARY_COLOR,
        spaceBefore=15,
        spaceAfter=8,
        fontName='Helvetica-Bold'
    )
    
    # Style paragraphe
    para_style = ParagraphStyle(
        'CustomParagraph',
        parent=styles['BodyText'],
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=10
    )
    
    # Style liste
    bullet_style = ParagraphStyle(
        'BulletList',
        parent=styles['BodyText'],
        fontSize=10,
        leading=13,
        leftIndent=20,
        bulletIndent=10,
        spaceAfter=5
    )
    
    # Contenu du document
    story = []
    
    # === PAGE DE COUVERTURE ===
    story.append(Spacer(1, 3*cm))
    story.append(Paragraph("💊 PharmaShop", title_style))
    story.append(Spacer(1, 0.3*cm))
    
    cover_title = ParagraphStyle(
        'CoverTitle',
        parent=title_style,
        fontSize=20,
        textColor=black
    )
    story.append(Paragraph("Digital Twin — Centre d'Assistance Client", cover_title))
    story.append(Spacer(1, 1*cm))
    
    cover_subtitle = ParagraphStyle('CoverSubtitle', parent=para_style, 
                                     fontSize=14, alignment=TA_CENTER, 
                                     textColor=HexColor('#555555'))
    story.append(Paragraph("<b>Rapport Technique</b>", cover_subtitle))
    story.append(Paragraph("Base de données PostgreSQL & Dashboard BI", cover_subtitle))
    
    story.append(Spacer(1, 2*cm))
    
    # Informations du projet
    info_data = [
        ['Auteur:', 'Samar'],
        ['Date:', datetime.now().strftime('%d %B %Y')],
        ['Projet:', 'Système multi-agents pour centre d\'assistance'],
        ['Domaine:', 'E-commerce & Parapharmacie (Tunisie)'],
        ['Technologies:', 'PostgreSQL, Python, Streamlit, React, FastAPI']
    ]
    
    info_table = Table(info_data, colWidths=[4*cm, 10*cm])
    info_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
        ('TEXTCOLOR', (0, 0), (0, -1), PRIMARY_COLOR),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(info_table)
    
    story.append(PageBreak())
    
    # === SOMMAIRE ===
    story.append(Paragraph("📑 Table des matières", section_style))
    story.append(Spacer(1, 0.5*cm))
    
    toc_items = [
        "1. Introduction et contexte du projet",
        "2. Architecture de la base de données PostgreSQL",
        "   2.1. Tables principales",
        "   2.2. Vues Business Intelligence",
        "3. API Dashboard BI",
        "   3.1. Endpoints FastAPI",
        "   3.2. Intégration frontend-backend",
        "4. Dashboard Streamlit",
        "   4.1. Architecture et fonctionnalités",
        "   4.2. Pages et visualisations",
        "5. Dashboard React intégré",
        "6. Diagramme d'architecture",
        "7. Métriques et KPIs disponibles",
        "8. Conclusion et perspectives"
    ]
    
    for item in toc_items:
        story.append(Paragraph(f"• {item}", bullet_style))
    
    story.append(PageBreak())
    
    # === 1. INTRODUCTION ===
    story.append(Paragraph("1. Introduction et contexte du projet", section_style))
    
    intro_text = """
    Ce rapport documente la contribution apportée au projet <b>Digital Twin</b> du centre d'assistance client 
    pour la parapharmacie en ligne tunisienne <b>MaPara</b>. Le projet implémente un système multi-agents 
    orchestrant six composants principaux : Client Simulator, Customer Advisor (RAG), Quality Analyst, 
    Workforce Manager, Result & Optimization et Digital Twin.
    """
    story.append(Paragraph(intro_text, para_style))
    story.append(Spacer(1, 0.3*cm))
    
    contribution_text = """
    <b>Ma contribution se concentre sur deux piliers essentiels :</b>
    """
    story.append(Paragraph(contribution_text, para_style))
    story.append(Spacer(1, 0.2*cm))
    
    story.append(Paragraph("• <b>Base de données PostgreSQL</b> : Conception et implémentation du schéma complet " +
                          "incluant 6 tables relationnelles et 7 vues optimisées pour l'analyse BI", bullet_style))
    story.append(Paragraph("• <b>Dashboards BI</b> : Développement de deux interfaces de visualisation " +
                          "(Streamlit standalone et React intégré) avec endpoints API FastAPI", bullet_style))
    
    story.append(Spacer(1, 0.5*cm))
    
    objectifs_text = """
    <b>Objectifs du système de persistence et de visualisation :</b><br/>
    • Traçabilité complète des interactions client-conseiller simulées<br/>
    • Analyse en temps réel des performances du centre d'assistance<br/>
    • Identification des points faibles et opportunités d'amélioration<br/>
    • Support à la prise de décision opérationnelle basée sur les données<br/>
    • Visualisation intuitive des KPIs pour différents profils d'utilisateurs
    """
    story.append(Paragraph(objectifs_text, para_style))
    
    story.append(PageBreak())
    
    # === 2. BASE DE DONNÉES ===
    story.append(Paragraph("2. Architecture de la base de données PostgreSQL", section_style))
    
    db_intro = """
    La base de données <b>callverse</b> constitue le cœur du système de persistence. Elle stocke l'intégralité 
    du cycle de vie des conversations : depuis la génération du profil client jusqu'aux décisions du Workforce Manager, 
    en passant par les évaluations qualité. L'architecture relationnelle garantit l'intégrité référentielle et 
    optimise les requêtes analytiques.
    """
    story.append(Paragraph(db_intro, para_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Tables principales
    story.append(Paragraph("2.1. Tables principales", subsection_style))
    
    tables_data = [
        ['<b>Table</b>', '<b>Description</b>', '<b>Champs clés</b>'],
        ['sim_clients', 'Profils clients simulés uniques', 'name, age, city, profile'],
        ['sim_conversations', 'Conversations complètes avec métadonnées', 'id, profile, topic, urgency, rag, client_id'],
        ['sim_turns', 'Messages individuels (client/advisor)', 'turn, role, content, latency_ms, intent, modules'],
        ['sim_sources', 'Sources RAG utilisées par message', 'source_id, title, module, score'],
        ['quality_evaluations', 'Évaluations de l\'Analyste Qualité', 'global_score, criteria (6), priority, alerts'],
        ['workforce_decisions', 'Décisions du Workforce Manager', 'status, problems, actions, has_escalation']
    ]
    
    tables_table = Table(tables_data, colWidths=[4*cm, 6*cm, 6*cm], repeatRows=1)
    tables_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#f9f9f9')]),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(tables_table)
    story.append(Spacer(1, 0.5*cm))
    
    indexes_text = """
    <b>Optimisations appliquées :</b><br/>
    • Indexes sur colonnes fréquemment interrogées (profile, topic, created_at, global_score, priority)<br/>
    • Contraintes de clés étrangères avec CASCADE pour maintenir l'intégrité<br/>
    • Contraintes UNIQUE pour éviter les doublons (client, conversation+turn+role)<br/>
    • Type JSONB pour stocker les rapports complets avec possibilité de requêtes JSON
    """
    story.append(Paragraph(indexes_text, para_style))
    
    story.append(PageBreak())
    
    # Vues BI
    story.append(Paragraph("2.2. Vues Business Intelligence", subsection_style))
    
    views_intro = """
    Sept vues matérialisées facilitent l'interrogation des données pour le reporting et l'analyse. 
    Elles pré-calculent les agrégations complexes et les jointures multi-tables, optimisant ainsi 
    les performances des dashboards.
    """
    story.append(Paragraph(views_intro, para_style))
    story.append(Spacer(1, 0.3*cm))
    
    views_data = [
        ['<b>Vue</b>', '<b>Objectif</b>', '<b>Métriques calculées</b>'],
        ['v_powerbi_turns', 
         'Vue denormalisée pour Power BI', 
         '1 ligne par message avec contexte complet'],
        
        ['v_bi_full', 
         'Vue analytique 360°', 
         'Jointure conversation + qualité + workforce'],
        
        ['v_daily_kpis', 
         'KPIs journaliers agrégés', 
         'Score moyen, taux escalade, nb alertes critiques, latence'],
        
        ['v_profile_perf', 
         'Performance par profil client', 
         'Score/critères moyens, taux escalade par profil (8 profils)'],
        
        ['v_topic_analysis', 
         'Analyse par thématique', 
         'Volume, score, risques par topic (12 thématiques)'],
        
        ['v_escalation_log', 
         'Journal des escalades', 
         'Conversations critiques + problèmes + actions déclenchées'],
        
        ['v_criteria_scores', 
         'Scores détaillés par critère', 
         'Format long pour graphiques radar (6 critères qualité)']
    ]
    
    views_table = Table(views_data, colWidths=[4*cm, 5.5*cm, 6.5*cm], repeatRows=1)
    views_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), SECONDARY_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#f0f9ff')]),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(views_table)
    
    story.append(Spacer(1, 0.5*cm))
    
    example_text = """
    <b>Exemple de vue v_daily_kpis (extrait SQL) :</b><br/>
    <font face="Courier" size="8">
    SELECT DATE(c.created_at) AS day,<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;COUNT(DISTINCT c.id) AS nb_conversations,<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;ROUND(AVG(q.global_score)::NUMERIC, 1) AS avg_quality_score,<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;ROUND(100.0 * COUNT(CASE WHEN w.has_escalation THEN 1 END)<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;/ NULLIF(COUNT(DISTINCT c.id), 0), 1) AS escalation_rate_pct<br/>
    FROM sim_conversations c<br/>
    LEFT JOIN quality_evaluations q ON q.conversation_id = c.id<br/>
    LEFT JOIN workforce_decisions w ON w.conversation_id = c.id<br/>
    GROUP BY DATE(c.created_at)
    </font>
    """
    story.append(Paragraph(example_text, para_style))
    
    story.append(PageBreak())
    
    # === 3. API DASHBOARD ===
    story.append(Paragraph("3. API Dashboard BI", section_style))
    
    api_intro = """
    Le module <b>backend/routes/dashboard.py</b> expose 9 endpoints FastAPI interrogeant directement 
    les vues PostgreSQL. Ces endpoints servent les deux dashboards (React et Streamlit) avec des 
    données formatées JSON prêtes à la visualisation.
    """
    story.append(Paragraph(api_intro, para_style))
    story.append(Spacer(1, 0.5*cm))
    
    story.append(Paragraph("3.1. Endpoints FastAPI", subsection_style))
    
    endpoints_data = [
        ['<b>Endpoint</b>', '<b>Méthode</b>', '<b>Description</b>'],
        ['/api/dashboard/kpis', 'GET', 'KPIs globaux (nb conversations, score moyen, taux résolution/escalade)'],
        ['/api/dashboard/criteria', 'GET', 'Scores moyens des 6 critères qualité'],
        ['/api/dashboard/profiles', 'GET', 'Performance par profil client (8 profils)'],
        ['/api/dashboard/trends?days=30', 'GET', 'Évolution temporelle des KPIs'],
        ['/api/dashboard/workforce-stats', 'GET', 'Statut et actions Workforce Manager'],
        ['/api/dashboard/alerts?limit=10', 'GET', 'Alertes critiques récentes (vue escalation_log)'],
        ['/api/dashboard/conversations', 'GET', 'Conversations récentes avec filtres (profile, topic)'],
        ['/api/dashboard/topics', 'GET', 'Analyse par thématique (12 topics)'],
        ['/api/dashboard/client-distribution', 'GET', 'Distribution clients par profil avec pourcentages']
    ]
    
    endpoints_table = Table(endpoints_data, colWidths=[5*cm, 2*cm, 9*cm], repeatRows=1)
    endpoints_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#faf5ff')]),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(endpoints_table)
    
    story.append(Spacer(1, 0.5*cm))
    
    fallback_text = """
    <b>Mécanisme de fallback :</b> En cas d'absence de PostgreSQL, l'API bascule automatiquement sur 
    une base SQLite locale pour les évaluations qualité, garantissant la continuité du service en mode dégradé.
    """
    story.append(Paragraph(fallback_text, para_style))
    
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("3.2. Intégration frontend-backend", subsection_style))
    
    integration_text = """
    Le fichier <b>dt-front/src/api/client.js</b> encapsule tous les appels API avec gestion d'erreurs centralisée. 
    Un mode <i>mock</i> permet le développement frontend sans backend actif (VITE_USE_MOCK=true). 
    Le proxy Vite (/api/* → http://localhost:8000) évite les problèmes CORS en développement.
    """
    story.append(Paragraph(integration_text, para_style))
    
    story.append(PageBreak())
    
    # === 4. DASHBOARD STREAMLIT ===
    story.append(Paragraph("4. Dashboard Streamlit", section_style))
    
    streamlit_intro = """
    Le dashboard Streamlit (<b>dashboard/app.py</b>) offre une interface d'analyse avancée connectée 
    directement à PostgreSQL via psycopg2. Il se déploie indépendamment du backend FastAPI et cible 
    les analystes métier et data scientists.
    """
    story.append(Paragraph(streamlit_intro, para_style))
    story.append(Spacer(1, 0.5*cm))
    
    story.append(Paragraph("4.1. Architecture et fonctionnalités", subsection_style))
    
    streamlit_features = """
    • <b>Connexion directe PostgreSQL</b> : Utilisation de psycopg2 avec cache Streamlit (@st.cache_resource)<br/>
    • <b>Visualisations Plotly</b> : Graphiques interactifs (line, bar, pie, radar, scatter)<br/>
    • <b>Thème sombre personnalisé</b> : Catppuccin Mocha (cohérence visuelle avec le frontend)<br/>
    • <b>Filtrage dynamique</b> : Par profil, thème, période temporelle<br/>
    • <b>Drill-down conversationnel</b> : Exploration détaillée message par message<br/>
    • <b>Rafraîchissement en temps réel</b> : Bouton de reload avec cache invalidation
    """
    story.append(Paragraph(streamlit_features, para_style))
    
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("4.2. Pages et visualisations", subsection_style))
    
    pages_data = [
        ['<b>Page</b>', '<b>Visualisations</b>', '<b>Cas d\'usage</b>'],
        ['📊 Vue globale', 
         'KPIs cards, histogramme scores, pie chart statut WF, bar chart actions',
         'Aperçu instantané de la santé du centre'],
        
        ['📈 Tendances temporelles', 
         'Line chart score qualité, bar+line volume/escalades, multi-line critères',
         'Analyse de l\'évolution dans le temps'],
        
        ['🎭 Analyse par profil', 
         'Bar chart horizontal par profil, tableau détaillé avec min/max',
         'Identification des profils problématiques'],
        
        ['🔬 Critères qualité', 
         'Radar spider chart 6 critères, bar chart avec seuil 75, pie priorités',
         'Focus sur la qualité des réponses'],
        
        ['⚠️ Alertes & Escalades', 
         'Liste expandable conversations critiques avec détails problèmes/actions',
         'Gestion des situations à risque'],
        
        ['📋 Conversations récentes', 
         'Dataframe filtrable + drill-down tour par tour avec métadonnées',
         'Investigation détaillée']
    ]
    
    pages_table = Table(pages_data, colWidths=[4*cm, 6*cm, 6*cm], repeatRows=1)
    pages_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), SUCCESS_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#f0fdf4')]),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(pages_table)
    
    story.append(Spacer(1, 0.5*cm))
    
    command_text = """
    <b>Commande de lancement :</b><br/>
    <font face="Courier" size="9">
    cd C:/Users/samar/Desktop/PI/dashboard<br/>
    streamlit run app.py
    </font><br/><br/>
    Le dashboard sera accessible sur <b>http://localhost:8501</b>
    """
    story.append(Paragraph(command_text, para_style))
    
    story.append(PageBreak())
    
    # === 5. DASHBOARD REACT ===
    story.append(Paragraph("5. Dashboard React intégré", section_style))
    
    react_intro = """
    Le composant <b>dt-front/src/pages/Dashboard.jsx</b> offre une visualisation intégrée dans l'application 
    web principale. Basé sur Chart.js (react-chartjs-2), il consomme les mêmes endpoints API que le dashboard 
    Streamlit mais s'intègre dans le flux utilisateur du Digital Twin.
    """
    story.append(Paragraph(react_intro, para_style))
    story.append(Spacer(1, 0.5*cm))
    
    react_features = """
    <b>Caractéristiques techniques :</b><br/>
    • <b>Framework</b> : React 18 + Vite + React Router<br/>
    • <b>Graphiques</b> : Chart.js v4 (Line, Bar, Doughnut, Radar)<br/>
    • <b>État</b> : React Hooks (useState, useCallback, useRef)<br/>
    • <b>Styling</b> : CSS-in-JS avec thème Catppuccin<br/>
    • <b>Icônes</b> : Lucide React (BarChart2, TrendingUp, AlertTriangle...)<br/>
    • <b>Responsive</b> : Grid layout adaptatif avec cartes KPI réutilisables<br/>
    • <b>Auto-refresh</b> : Polling optionnel toutes les 30 secondes
    """
    story.append(Paragraph(react_features, para_style))
    
    story.append(Spacer(1, 0.5*cm))
    
    components_text = """
    <b>Composants React développés :</b><br/>
    • <b>KpiCard</b> : Carte KPI avec icône, valeur, tendance et indicateur visuel<br/>
    • <b>ChartCard</b> : Wrapper pour graphiques Chart.js avec titre et hauteur fixe<br/>
    • <b>SectionTitle</b> : En-tête de section stylisé<br/>
    • <b>ScoreBadge</b> : Badge coloré selon seuils (≥75 vert, 60-74 orange, <60 rouge)<br/>
    • <b>Dashboard</b> : Composant principal orchestrant 6 onglets dynamiques
    """
    story.append(Paragraph(components_text, para_style))
    
    story.append(Spacer(1, 0.5*cm))
    
    tabs_text = """
    <b>Onglets du dashboard React :</b><br/>
    1. <b>Overview</b> : KPIs globaux + distribution scores + statut workforce + actions<br/>
    2. <b>Performance</b> : Graphiques par profil client et par thématique<br/>
    3. <b>Quality</b> : Radar des critères + distribution priorités + tendances<br/>
    4. <b>Trends</b> : Évolution temporelle (30 derniers jours)<br/>
    5. <b>Alerts</b> : Liste des conversations escaladées avec drill-down<br/>
    6. <b>Details</b> : Conversations récentes avec filtres et pagination
    """
    story.append(Paragraph(tabs_text, para_style))
    
    story.append(PageBreak())
    
    # === 6. DIAGRAMME ===
    story.append(Paragraph("6. Diagramme d'architecture de la stack BI", section_style))
    
    arch_intro = """
    Le schéma ci-dessous illustre le flux de données complet depuis les agents jusqu'aux dashboards, 
    en passant par la couche de persistence PostgreSQL et l'API FastAPI.
    """
    story.append(Paragraph(arch_intro, para_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Diagramme ASCII art amélioré
    diagram_text = """
    <font face="Courier" size="7">
    ┌─────────────────────────────────────────────────────────────────────────┐<br/>
    │                    AGENTS MULTI-ÉTAPES (Pipeline)                        │<br/>
    ├───────────┬──────────────┬──────────────┬─────────────┬─────────────────┤<br/>
    │  Client   │   Customer   │   Quality    │  Workforce  │  Result &amp;       │<br/>
    │ Simulator │   Advisor    │   Analyst    │   Manager   │ Optimization    │<br/>
    │  (Agent1) │   (Agent2)   │   (Agent3)   │  (Agent4)   │   (Agent5)      │<br/>
    └─────┬─────┴──────┬───────┴──────┬───────┴──────┬──────┴─────────────────┘<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;└────────────┴──────────────────┴──────────────────┘<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;▼<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;┌──────────────────────────────────────────────┐<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│   services/simulation.py (save_to_db)        │<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│   • save_conversation()                      │<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│   • save_quality_evaluation()                │<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│   • save_workforce_decision()                │<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;└─────────────────────┬────────────────────────┘<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;▼<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;╔═══════════════════════════════════════════════╗<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║       POSTGRESQL DATABASE: callverse          ║<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;╟───────────────────────────────────────────────╢<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║  TABLES (6):                                  ║<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║  • sim_clients                                ║<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║  • sim_conversations                          ║<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║  • sim_turns                                  ║<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║  • sim_sources                                ║<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║  • quality_evaluations                        ║<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║  • workforce_decisions                        ║<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;╟───────────────────────────────────────────────╢<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║  VUES BI (7):                                 ║<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║  • v_powerbi_turns (Power BI export)          ║<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║  • v_bi_full (jointure 360°)                  ║<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║  • v_daily_kpis                               ║<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║  • v_profile_perf                             ║<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║  • v_topic_analysis                           ║<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║  • v_escalation_log                           ║<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║  • v_criteria_scores                          ║<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;╚═══════════════════════════════════════════════╝<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;┌────────────┴────┐&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;▼&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>
    ┌─────────────────────┐&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>
    │  FastAPI Backend    │&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>
    │  (routes/           │&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>
    │   dashboard.py)     │&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>
    │  9 Endpoints API    │&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>
    │  :8000/api/         │&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>
    │  dashboard/*        │&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>
    └──────┬──────────────┘&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;▼&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;▼&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;▼<br/>
    ┌──────────────────┐&nbsp;&nbsp;&nbsp;&nbsp;┌─────────────────┐&nbsp;&nbsp;┌──────────────┐<br/>
    │  React Dashboard │&nbsp;&nbsp;&nbsp;&nbsp;│Streamlit Dashbrd│&nbsp;&nbsp;│  Power BI    │<br/>
    │  (Dashboard.jsx) │&nbsp;&nbsp;&nbsp;&nbsp;│  (app.py)       │&nbsp;&nbsp;│  (Export)    │<br/>
    │  Chart.js        │&nbsp;&nbsp;&nbsp;&nbsp;│  Plotly         │&nbsp;&nbsp;│  Direct DB   │<br/>
    │  :5173/dashboard │&nbsp;&nbsp;&nbsp;&nbsp;│  :8501          │&nbsp;&nbsp;│  Connection  │<br/>
    └──────────────────┘&nbsp;&nbsp;&nbsp;&nbsp;└─────────────────┘&nbsp;&nbsp;└──────────────┘<br/>
    </font>
    """
    story.append(Paragraph(diagram_text, para_style))
    
    story.append(PageBreak())
    
    # === 7. MÉTRIQUES ===
    story.append(Paragraph("7. Métriques et KPIs disponibles", section_style))
    
    metrics_intro = """
    Le système expose plus de 40 métriques calculées automatiquement à partir des données de simulation. 
    Elles sont regroupées en 5 catégories principales.
    """
    story.append(Paragraph(metrics_intro, para_style))
    story.append(Spacer(1, 0.5*cm))
    
    metrics_data = [
        ['<b>Catégorie</b>', '<b>Métriques</b>'],
        ['Volume & Performance', 
         '• Nombre total de conversations\n' +
         '• Nombre de clients uniques\n' +
         '• Nombre de tours de conversation\n' +
         '• Latence moyenne (ms)\n' +
         '• Temps de traitement par agent'],
        
        ['Qualité', 
         '• Score global moyen (/100)\n' +
         '• Scores par critère (pertinence, exactitude, groundedness, empathie, clarté, conformité)\n' +
         '• Distribution des scores (histogramme)\n' +
         '• Taux de conversations ≥75/100'],
        
        ['Risques & Alertes', 
         '• Nombre d\'alertes critiques\n' +
         '• Taux de priorité élevée/critique (%)\n' +
         '• Taux d\'escalade humaine (%)\n' +
         '• Conversations nécessitant revue humaine\n' +
         '• Classification LoRA (OK/CRITIQUE)'],
        
        ['Workforce', 
         '• Statut OPTIMAL vs INTERVENTION_REQUISE\n' +
         '• Taux de résolution automatique (%)\n' +
         '• Actions déclenchées par type (escalade, formation, KB, RAG)\n' +
         '• Impact staffing\n' +
         '• Modules de formation suggérés'],
        
        ['Segmentation', 
         '• Performance par profil client (8 profils)\n' +
         '• Performance par thématique (12 topics)\n' +
         '• Distribution clients par profil (%)\n' +
         '• Comparaison min/max/moyenne par segment\n' +
         '• Tendances temporelles (jour/semaine/mois)']
    ]
    
    metrics_table = Table(metrics_data, colWidths=[4*cm, 12*cm], repeatRows=1)
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DANGER_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
        ('FONT', (0, 1), (0, -1), 'Helvetica-Bold', 9),
        ('FONT', (1, 1), (1, -1), 'Helvetica', 8),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#fef2f2')]),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(metrics_table)
    
    story.append(PageBreak())
    
    # === 8. CONCLUSION ===
    story.append(Paragraph("8. Conclusion et perspectives", section_style))
    
    achievements_text = """
    <b>Réalisations accomplies :</b><br/><br/>
    
    ✅ <b>Base de données robuste</b> : Schéma PostgreSQL complet avec 6 tables et 7 vues BI optimisées, 
    garantissant la traçabilité end-to-end des conversations et facilitant les analyses complexes.<br/><br/>
    
    ✅ <b>API Dashboard unifiée</b> : 9 endpoints FastAPI exposant les données de manière cohérente avec 
    gestion d'erreurs centralisée et mécanisme de fallback SQLite.<br/><br/>
    
    ✅ <b>Double interface de visualisation</b> : Dashboard Streamlit pour les analystes métier 
    (6 pages, 15+ graphiques Plotly) et dashboard React intégré pour les utilisateurs finaux 
    (6 onglets, Chart.js).<br/><br/>
    
    ✅ <b>Intégration complète</b> : Flux de données automatisé depuis les agents jusqu'aux visualisations 
    sans intervention manuelle.<br/><br/>
    
    ✅ <b>Performance optimisée</b> : Vues matérialisées avec agrégations pré-calculées, indexes stratégiques, 
    et cache Streamlit réduisant les temps de requête.
    """
    story.append(Paragraph(achievements_text, para_style))
    
    story.append(Spacer(1, 0.5*cm))
    
    perspectives_text = """
    <b>Perspectives d'amélioration :</b><br/><br/>
    
    🔮 <b>Export Power BI natif</b> : Connecteur DirectQuery exploitant v_powerbi_turns pour rapports 
    exécutifs avec drill-through.<br/><br/>
    
    🔮 <b>Alertes temps réel</b> : Système de notifications push (WebSocket) pour escalades critiques 
    détectées par le Workforce Manager.<br/><br/>
    
    🔮 <b>ML Pipeline</b> : Intégration de modèles prédictifs (régression, classification) pour anticiper 
    les risques d'escalade avant évaluation qualité.<br/><br/>
    
    🔮 <b>A/B Testing</b> : Framework pour comparer différentes versions de prompts/modèles avec métriques 
    statistiques (Student t-test, effet de taille).<br/><br/>
    
    🔮 <b>Audit Trail</b> : Journalisation des modifications de configuration et des décisions critiques 
    avec conformité RGPD/CNIL.<br/><br/>
    
    🔮 <b>Multi-tenancy</b> : Support de plusieurs clients/centres avec isolation des données et 
    dashboards personnalisés par tenant.
    """
    story.append(Paragraph(perspectives_text, para_style))
    
    story.append(Spacer(1, 0.5*cm))
    
    final_text = """
    Ce système de persistence et de visualisation constitue la <b>colonne vertébrale analytique</b> 
    du Digital Twin. Il transforme les simulations brutes en insights actionnables, permettant 
    l'amélioration continue du centre d'assistance client par une approche data-driven rigoureuse.
    """
    story.append(Paragraph(final_text, para_style))
    
    story.append(Spacer(1, 1*cm))
    
    # Signature
    signature_style = ParagraphStyle('Signature', parent=para_style, 
                                      alignment=TA_CENTER, fontSize=11, 
                                      textColor=PRIMARY_COLOR)
    story.append(Paragraph("━━━━━━━━━━━━━━━━━━━", signature_style))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("<b>Samar</b>", signature_style))
    story.append(Paragraph("Développeur Base de données & BI", signature_style))
    story.append(Paragraph(f"{datetime.now().strftime('%B %Y')}", signature_style))
    
    # Construction du PDF
    doc.build(story, onFirstPage=lambda c, d: (add_header(c, d), add_footer(c, d)),
              onLaterPages=lambda c, d: (add_header(c, d), add_footer(c, d)))
    
    print(f"✅ PDF généré avec succès : {OUTPUT_PATH}")
    return OUTPUT_PATH

if __name__ == "__main__":
    create_pdf()
