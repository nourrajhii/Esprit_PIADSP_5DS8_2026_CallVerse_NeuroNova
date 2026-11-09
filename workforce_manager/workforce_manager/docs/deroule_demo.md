# Déroulé de la démo devant le jury (≈ 12 minutes)

Toutes les commandes se lancent depuis `C:\Users\yosri\Desktop\pi`. Chaque commande a été chronométrée en répétition.

---

## La veille au soir (15 min)

1. **Vérifier que tout marche** (2 minutes) :
   ```powershell
   python -m pytest workforce_manager/tests -q
   ```
   Attendu : `267 passed`.
2. **Répéter une fois les 3 commandes de la démo** (section « Pendant la démo »).
3. **Copier l'archive sur une clé USB** : `livraison\callverse_workforce_manager.zip`, en cas de panne du PC.
4. **Ouvrir à l'avance, dans l'explorateur, les 4 images** de `workforce_manager\evaluation\figures\` :
   - `ppo_courbe.png` ;
   - `comparaison_recompenses.png` ;
   - `generalisation_volume.png` ;
   - `comparaison_sami_abandons.png`.

## Le matin, 10 minutes avant

1. **Ouvrir 2 terminaux PowerShell** dans `C:\Users\yosri\Desktop\pi`. Dans chacun, taper `chcp 65001` pour que les accents s'affichent bien.
2. **Agrandir la police du terminal** (Ctrl + molette) : le jury doit pouvoir lire depuis le fond de la salle.
3. **Terminal 2 : lancer l'API** et la laisser tourner :
   ```powershell
   python -m uvicorn workforce_manager.api.main:app --port 8000
   ```
   Ouvrir ensuite **http://localhost:8000/docs** dans le navigateur. Si le port 8000 est occupé, utiliser `--port 8001`.
4. **Gemini (facultatif)** : le quota gratuit est de 20 requêtes par jour et une démo en utilise 1. En cas de doute, garde `--sans-llm` : la démo reste complète, avec les textes fixes.

---

## Pendant la démo

### 0. Introduction (1 min) – rien à l'écran
Dis le texte de 2 minutes (`docs/presentation_orale.md`), version courte :
> « Mon agent pilote le centre de PharmaShop à deux niveaux. Il apprend par Reinforcement Learning dans le Digital Twin, et il est responsable : il sait quand il ne sait pas, propose ses dépenses à un humain et explique chacune de ses décisions. »

### 1. L'apprentissage (1 min) – image `ppo_courbe.png`
> « Voici la boucle état → action → récompense, répétée sur 12 500 journées. La récompense passe de 3 à 338 : l'agent a appris. »

### 2. Démo en direct : Inès, pic d'activité (2 min)
```powershell
python -m workforce_manager.demo --persona ines --pause 1 --sans-llm --journees 10
```
Durée : environ 15 s avec la pause. Ce qu'il faut pointer à l'écran :
- chaque heure, la **situation**, les **décisions avec leur confiance**, puis l'**effet** (clients perdus avec l'agent face aux règles) ;
- **à 18h15, l'appel d'Inès** : l'évaluation qualité, puis la décision des règles (escalade vers un humain, priorité haute) ;
- **en fin de journée** : 28 clients perdus avec l'agent contre 77 avec les règles, et le tableau avant/après (abandons 9,1 % → 3,2 %).

### 3. Démo en direct : vous validez les dépenses (2 min) – le moment fort
```powershell
python -m workforce_manager.demo --persona sami --superviseur 3 --sans-llm --journees 10
```
L'agent te pose **3 questions o/n** :
- réponds **o** à la première ;
- réponds **n** à la deuxième, pour montrer que le refus est respecté ;
- laisse le **prof répondre** à la troisième.

Ensuite :
> « La grille dit "proposer l'activation de conseillers" : mon agent propose, l'humain décide. Après mes 3 réponses, il agit dans un budget délégué, et chaque refus est tracé dans le journal. »

Montre la ligne `JOURNAL : … propositions coûteuses dont … refusées`.

### 4. Démo en direct : une crise jamais vue (2 min)
```powershell
python -m workforce_manager.demo --persona crise --pause 1 --sans-llm --journees 10
```
À pointer :
- dès 10h, la ligne **« SITUATION INCONNUE -> repli sur les règles : 2 événements simultanés (jamais plus de 1 à l'entraînement) »** ;
- en fin de journée, **27 replis**.

> « Un agent responsable sait quand il sort de ce qu'il a appris. Ici, il passe la main au lieu d'improviser, et le résultat est meilleur que le PPO seul. »

### 5. L'API pour l'équipe (1 min) – navigateur, http://localhost:8000/docs
- **`POST /api/agents/workforce-manager`** → Try it out → exemple « Inès » → Execute. On obtient le contrat, avec le responsable de chaque action.
- **`POST …/simulate-day`** → `{"scenario": "sous_effectif", "policy": "responsable"}` → montrer le champ **`journal`** : qui a décidé, pourquoi, avec quelle confiance, validé par qui.

### 6. Les preuves (2 min) – images
- `comparaison_recompenses.png` : « Sur les 8 situations de la grille, l'agent (en rose) bat les règles, de 41 à 50 journées sur 50. »
- `generalisation_volume.png` : « Sur 100 journées jamais vues, il bat les règles 92 fois sur 100. »
- `docs/conformite_grille.md` : « Chaque ligne de votre grille, avec où elle est réalisée. »

### 7. Conclusion (30 s)
> « Un agent qui apprend, qui bat le chef de plateau dans toutes les situations demandées, et qui reste responsable : il s'arrête quand il ne sait pas, demande avant de dépenser, et explique tout. Ses limites sont mesurées et documentées. »

---

## Plans de secours

| Problème | Solution |
|---|---|
| Une commande plante | Montrer les journaux déjà enregistrés : `workforce_manager\evaluation\resultats\journaux\journal_ines.json` (et `_sami`, `_karim`, `_crise`), ainsi que les figures. |
| Le port 8000 est occupé | `--port 8001`, puis http://localhost:8001/docs |
| Pas d'internet ou Gemini indisponible | Toujours utiliser `--sans-llm`. L'API renvoie les textes fixes (en-tête `X-Explication-Source: fallback`) et c'est un argument : « l'agent ne dépend pas du LLM pour décider ». |
| Accents illisibles | `chcp 65001`, puis relancer |
| Le PC ne démarre pas | Clé USB : décompresser l'archive sur un autre PC et suivre `GUIDE_EXECUTION.md` (environ 15 min). Sinon, présenter avec les figures et `docs/agent_responsable.md`. |
| Le prof veut une autre journée | `--graine N` (n'importe quel nombre) : le résultat varie. Rappeler que la preuve, ce sont les 50 journées de chaque scénario, pas une seule. |

## Si le jury demande « pourquoi cette journée ? »
> « Pour chaque persona, je montre la **journée médiane** : celle où l'écart entre l'agent et les règles est le plus proche de l'écart médian sur 50 journées. Ce n'est ni la meilleure ni la pire. Vous pouvez en choisir une autre avec `--graine`. »
