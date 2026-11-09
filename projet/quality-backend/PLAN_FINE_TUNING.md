# Protocole de fine-tuning — Quality Analyst E-commerce / Santé

**État au 22 octobre 2026 : PAS ENCORE ENTRAÎNÉ.** Gemini 3.6 Flash sert de référence (baseline via API).

## Objectif

Entraîner un petit modèle open-weight avec des adaptateurs LoRA à évaluer les
conversations client–conseiller selon quatre critères : pertinence, empathie,
clarté, conformité, et signaler une violation critique.

## Données

- Construire un corpus **fictif** et diversifié, avec des procédures métier fiables.
- Prévoir des labels humains indépendants (au moins deux annotateurs sur une partie).
- Identifier les cas médicaux sensibles et les demandes de secrets ; distinguer
  une plainte du client d'une instruction fautive du conseiller.
- Le CSV de 10 cas actuel est **un pilote de validation**, pas un corpus
  d'entraînement ou une preuve que le modèle s'améliore.

## Expérience

1. Figer une grille de notation et arbitrer les désaccords humains.
2. Constituer des ensembles train / validation / test distincts, séparés **par
   scénario / famille de formulation**, pas par simple ligne si paraphrases.
3. Choisir un modèle open-weight entraînable et vérifier licence, matériel, quota.
4. Mesurer le modèle de base sur le test gelé.
5. Entraîner LoRA avec Hugging Face PEFT ; enregistrer le modèle, hyperparamètres,
   graine aléatoire, métriques et coût.
6. Évaluer le modèle entraîné sur **le même test gelé**.
7. Comparer MAE/RMSE, précision/rappel/F1 sur les violations critiques, et
   taux d'échecs techniques. Fournir la matrice de confusion, le support des
   classes, et examiner les faux négatifs médicaux.
8. Garder une barrière de sûreté externe pour les cas à haut risque, même si
   un modèle fine-tuné génère un score rassurant.

## Ce que dire au suivi du vendredi

« Nous disposons d'une baseline Gemini intégrée, d'annotations et d'un benchmark
exploratoire de huit évaluations appariées. Le fine-tuning est la phase suivante :
constitution d'un corpus annoté distinct, entraînement LoRA d'un modèle ouvert,
puis comparaison sur un jeu de test indépendant. »

Pas de revendication de fine-tuning réalisé sans entraînement et évaluation réels.
