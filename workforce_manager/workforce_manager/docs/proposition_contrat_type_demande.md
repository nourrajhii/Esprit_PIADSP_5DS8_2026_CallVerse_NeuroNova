# Proposition d'évolution du contrat – `type_demande` (Workforce Manager)

**Statut :** ⚠️ **remplacée par `openapi_workforce_manager_v2.yaml`**, qui reprend `type_demande` et ajoute
`request`, `kpi` et les champs de réponse utilisés par le front. Ce document reste pour l'historique.

## Problème

`POST /agents/workforce-manager` ne reçoit que `evaluation`. Le Workforce Manager ne sait
donc pas si la conversation portait sur une demande **standard**, **santé** ou **urgence**.
Or la décision en dépend :

- conformité < 70 sur une demande **santé** → `escalade_humain` (haute), pharmacien conseil ;
- même note sur une demande **standard** (CGV, livraison) → `ajuster_reponse` (moyenne) ;
- pertinence < 60 sur une **urgence** (cas d'Inès) → `escalade_humain` (haute).

Sans cette information, l'agent applique le principe de précaution (tout est traité comme
santé), ce qui produit des escalades inutiles vers le pharmacien.

## Modification proposée (rétrocompatible)

Un champ **optionnel** dans le corps de la requête. Rien ne change pour les agents qui ne
l'envoient pas.

```yaml
  /agents/workforce-manager:
    post:
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                evaluation: { $ref: '#/components/schemas/QualityEvaluation' }
                type_demande:
                  type: string
                  enum: [standard, sante, urgence]
                  description: >
                    Nature de la demande client. Optionnel : si absent, le Workforce
                    Manager traite la demande comme une demande santé (précaution).
```

## Qui fournit la valeur ?

- **Client Simulator** : la connaît déjà (scénario généré) ; il peut la mettre dans
  `ClientRequest.entities.type_demande` (champ libre existant, aucun changement de schéma).
- **Orchestrateur `/simulations`** : la recopie dans l'appel au Workforce Manager.
